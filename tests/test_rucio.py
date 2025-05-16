import pytest
import os
import uuid 

from rucio.client import Client
from rucio.client.uploadclient import UploadClient
from rucio.common.exception import Duplicate, ScopeNotFound, AccountNotFound, DataIdentifierNotFound, RucioException, RSEProtocolNotSupported

@pytest.fixture(scope="module")
def rucio_client():
    """Fixture to set the RUCIO_CONFIG environment variable before each test."""
    rucio_config = os.path.join(os.path.dirname(__file__), '..', 'rucio.cfg')
    os.environ['RUCIO_CONFIG'] = rucio_config
    # Assuming root account for setup/teardown if needed, adjust if necessary
    # You might need to configure auth based on your rucio.cfg or environment
    client = Client() # Let the client pick up rucio_host from rucio.cfg

    # Ensure 'user' scope exists for the test account (usually 'root' for tests)
    try:
        client.add_scope('root', 'user')
    except Duplicate:
        pass # Scope already exists
    yield client


def test_rucio_alive(rucio_client: Client):
    """Test if Rucio server is alive using ping."""
    # Attempt to ping the server
    result = rucio_client.ping()
    
    # Check if we got a response
    assert result is not None, "Ping returned None"
    assert isinstance(result, dict), "Ping should return a dictionary"
    assert 'version' in result, "Response should contain version information"

def test_add_and_delete_account(rucio_client: Client):
    """Test adding a user, verify it exists, then delete it."""
    # Rucio does a soft delete of usernames. Creating the same account name does not make it active. 
    # Therefore, need to use random names for testing. Truly stupid. 
    username = f'deleteme_{uuid.uuid4().hex[:12]}'
    try:
        rucio_client.add_account(username, 'USER', 'test@email.com')
    except Duplicate as e:
        pass
    
    # List all accounts to verify
    accounts = list(rucio_client.list_accounts())
    
    # Check if account exists
    account_exists = any(acc['account'] == username for acc in accounts)
    assert account_exists, f"Account {username} not found"
    
    assert rucio_client.delete_account(username), "Unable to delete account"

@pytest.mark.skip(reason="There is an unresolved issue with the RSE creation in the test environment.")
def test_upload_and_delete_file(rucio_client: Client):
    """Test uploading a file, verifying it exists, and then deleting it."""
    scope = 'user'
    filename = f'testfile_{uuid.uuid4().hex[:12]}.txt'
    filepath = os.path.join(os.path.dirname(__file__), 'testfile.txt')

    rse_name = 'MOCK'
    # Ensure the MOCK RSE exists and has a 'file' protocol
    try:
        rse_info = rucio_client.get_rse(rse=rse_name)
    except Exception as e:
        if 'RSE not found' in str(e):
            try:
                rucio_client.add_rse(rse=rse_name)
                rucio_client.add_rse_attribute(rse=rse_name, key='volatile', value=True)
                rse_info = rucio_client.get_rse(rse=rse_name) # Get updated info
            except Exception as add_rse_exception:
                assert False, f"Failed to add MOCK RSE: {add_rse_exception}"
        else:
            assert False, f"Unexpected error checking/adding RSE: {e}"

    # Add a 'file' protocol if MOCK RSE doesn't have one.
    # This is crucial for UploadClient to work correctly.
    # The prefix should point to a directory writable by the Rucio server.
    # In Rucio's Docker test environment, this is typically /tmp/rucio_tests/MOCK
    # Ensure this path exists and is writable in your Rucio server container.
    try:
        protocols = rucio_client.list_rse_protocols(rse_name)
        if not any(p['scheme'] == 'file' for p in protocols):
            protocol_attrs = {
                'scheme': 'file',
                'hostname': 'localhost', # For 'file' protocol, hostname is often localhost
                'port': 0,
                'prefix': f'/tmp/rucio_tests/{rse_name}', # Standard prefix for MOCK in tests
                'impl': 'rucio.rse.protocols.posix.Default',
                'domains': {
                    'lan': {'read': 1, 'write': 1, 'delete': 1},
                    'wan': {'read': 1, 'write': 1, 'delete': 1}}}
            rucio_client.add_protocol(rse_name, protocol_attrs)
    except Exception as e:
        assert False, f"Failed to add protocol to MOCK RSE: {e}"

    # Create a dummy file for upload
    with open(filepath, 'w') as f:
        f.write('This is a test file.')

    # Upload the file
    try:
        upload_client = UploadClient(rucio_client)
        status = upload_client.upload([{
            'path': filepath,
            'rse': rse_name,
            'did_scope': scope,
            'did_name': filename,
            'guid': uuid.uuid4().hex
        }])
        assert status == 0, "File upload failed"
    except RucioException as e:
        assert False, f"Failed to upload file: {e}"
    except Exception as e:
        assert False, f"Unexpected error during upload: {e}"


    # Check if the file exists
    try:
        did = rucio_client.get_did(scope, filename)
        assert did is not None, f"File {filename} not found after upload"
        assert did['name'] == filename, "File name mismatch"
        assert did['scope'] == scope, "File scope mismatch"
    except DataIdentifierNotFound as e:
        assert False, f"File {filename} not found after upload: {e}"

    # Delete the file
    try:
        rucio_client.delete_dids(dids=[{'scope': scope, 'name': filename}])
    except RucioException as e:
        assert False, f"Failed to delete file: {e}"

    # Check if the file was deleted
    try:
        rucio_client.get_did(scope, filename)
        assert False, f"File {filename} still exists after deletion"
    except DataIdentifierNotFound:
        pass
    except Exception as e:
        assert False, f"Unexpected error: {e}"

    # Clean up the dummy file
    os.remove(filepath)
