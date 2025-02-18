import pytest
import os

from rucio.client import Client
from rucio.common.exception import Duplicate

def set_rucio_config():
    """Fixture to set the RUCIO_CONFIG environment variable before each test."""
    rucio_config = os.path.join(os.path.dirname(__file__), '..', 'rucio.cfg')
    os.environ['RUCIO_CONFIG'] = rucio_config

@pytest.fixture(autouse=True)
def set_env():
    set_rucio_config()
    yield  # This allows the test to run
    # Optionally, you can clean up after tests here if needed

def test_rucio_alive():
    """Test if Rucio server is alive using ping."""
    try:
        # Initialize Rucio client with the localhost endpoint
        client = Client(rucio_host='https://localhost:10443',
                        auth_type='userpass',
                        creds={'username': 'ddmlab', 'password': 'secret'})
        
        # Attempt to ping the server
        result = client.ping()
        
        # Check if we got a response
        assert result is not None, "Ping returned None"
        assert isinstance(result, dict), "Ping should return a dictionary"
        assert 'version' in result, "Response should contain version information"
        
    except Exception as e:
        pytest.fail(f"Failed to connect to Rucio server: {str(e)}")

def test_add_account():
    """Test adding a user and verifying it exists."""
    try:
        # Initialize Rucio client
        client = Client(rucio_host='https://localhost:10443',
                       auth_type='userpass',
                       creds={'username': 'ddmlab', 'password': 'secret'})
        
        # First ensure the account exists
        try:
            client.add_account('testers', 'USER', 'test@email.com')
        except Duplicate:
            pass
        
        # List all accounts to verify
        accounts = list(client.list_accounts())
        
        # Check if account exists
        account_exists = any(acc['account'] == 'testers' for acc in accounts)
        assert account_exists, "Account 'testers' not found"
        
        client.delete_account('testers')
        
    except Exception as e:
        pytest.fail(f"Failed to add or verify user: {str(e)}")