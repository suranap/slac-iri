import pytest
import requests
import time
from functools import lru_cache
from .utils import fetch_slurm_token, fetch_nersc_token

# Define the base URL for the service
BASE_URL = 'http://127.0.0.1:10050'
SERVICE_VERSION_FOR_TESTS = 'v0.1.0' 

# Define backend configurations with tokens
BACKEND_CONFIGS = [
    {
        "name": "slac",
        "version": "v0.1.0",
        "token_func": lambda: fetch_slurm_token()
    },
    {
        "name": "nersc",
        "version": "v0.1.0",
        "token_func": lambda: fetch_nersc_token()
    }
]

@lru_cache(maxsize=1)
def get_available_backends():
    """Returns list of available backend configurations with valid tokens."""
    backends = []
    for config in BACKEND_CONFIGS:
        token = config['token_func']()
        if token is not None:
            backends.append((config['name'], config['version'], token))
    return backends

def pytest_generate_tests(metafunc):
    """pytest hook for dynamic test parameterization.
    
    This function is automatically called by pytest for each test function.
    For tests that require a 'backend_config' parameter, it:
    - Fetches available backends with valid authentication tokens
    - Skips all tests if no backends are available
    - Runs each test once per available backend
    
    Each backend_config is a tuple of (name, version, token).
    """
    if "backend_config" in metafunc.fixturenames:
        available_backends = get_available_backends()
        if not available_backends:
            pytest.skip("No backends available with valid tokens")
        metafunc.parametrize("backend_config", available_backends)

# Helper to construct auth headers
def _get_auth_headers_for_backend(token: str):
    return {"Authorization": f"Bearer {token}"} if token else {}

# --- Helper Function to Submit a Job ---
# This helps reduce code duplication in tests that need a job ID.
def submit_test_job(backend, api_version, token, executable="/usr/bin/sleep", args=["600"], name="api_test"):
    """Submits a simple job conforming to JobEx model and returns its ID."""
    headers = _get_auth_headers_for_backend(token)
    url = f'{BASE_URL}/api/{backend}/{api_version}/job'

    job_spec_data = {
        "name": name,
        "executable": executable,
        "arguments": args,
        # Using /tmp which is generally more accessible in containers/test envs
        "directory": "/tmp",
        "environment": {
            "PATH": "/bin:/usr/bin/:/usr/local/bin/",
            "LD_LIBRARY_PATH": "/lib/:/lib64/:/usr/local/lib"
        },
        "stdout_path": f"/tmp/{name}.out",
        "stderr_path": f"/tmp/{name}.err",
        "resources": {
            "node_count": 1,
            "process_count": 1
        }
    }

    job_ex_payload = {
        "spec": job_spec_data
    }
    resp = requests.post(url, json=job_ex_payload, headers=headers)
    # Raise an exception if submission fails (e.g., 4xx or 5xx error)
    resp.raise_for_status()
    assert resp.status_code == 201
    response_data = resp.json()
    assert "id" in response_data
    job_id = response_data["id"]
    print(f"Submitted test job with ID: {job_id}") # Added for visibility during tests
    # Give SLURM a moment to process the submission
    time.sleep(1)
    return job_id

# --- Health checks ---

def test_hello():
    resp = requests.get(f'{BASE_URL}/hello')
    assert resp.status_code == 200
    assert resp.text == '"Hello, world!"'

def test_global_health():
    """Tests the global health endpoint of the PSI/J service."""
    resp = requests.get(f'{BASE_URL}/health')
    assert resp.status_code == 200
    health_data = resp.json()
    assert health_data["status"] == "healthy"
    # assert health_data["service_version"] == SERVICE_VERSION_FOR_TESTS

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_backend_health(backend_config):
    """Tests the health endpoint for a specific backend."""
    backend, version, token = backend_config
    url = f'{BASE_URL}/api/{backend}/{version}/health'
    headers = _get_auth_headers_for_backend(token)
    resp = requests.get(url, headers=headers)
    # Check if the response status code is 200 (or handle potential errors like 503 if slurmrestd is down)
    if resp.status_code == 503 or resp.status_code == 504:
         pytest.skip(f"Backend '{backend}' health check at {url} failed: {resp.status_code} - {resp.text}")
    elif resp.status_code != 200:
         # Print details if it's another unexpected error
         print(f"Unexpected health check status for backend '{backend}' (version {version}): {resp.status_code}")
         print(f"Response body: {resp.text}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_submit_job(backend_config):
    backend, version, token = backend_config
    # Use the helper function for consistency
    job_id = submit_test_job(backend, version, token, name=f"submit_job_test_{backend}_{version}")
    assert isinstance(job_id, str)
    headers = _get_auth_headers_for_backend(token)
    # Optional: Clean up the job
    try:
        requests.delete(f'{BASE_URL}/api/{backend}/{version}/job/{job_id}', headers=headers)
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to clean up job {job_id} for backend {backend} in test_submit_job: {e}")


# --- Tests for Get Job Status ---

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_get_job_status_valid(backend_config):
    """Tests retrieving the status of a successfully submitted job."""
    backend, version, token = backend_config
    job_id = submit_test_job(backend, version, token, name=f"status_test_{backend}_{version}")
    headers = _get_auth_headers_for_backend(token)
    try:
        # Poll the job status until it's available or timeout occurs
        timeout = 10  # seconds
        interval = 1  # seconds
        elapsed = 0
        while elapsed < timeout:
            resp = requests.get(f'{BASE_URL}/api/{backend}/{version}/job/{job_id}', headers=headers)
            if resp.status_code == 200:
                break
            time.sleep(interval)
            elapsed += interval
        else:
            pytest.fail(f"Job status for backend {backend} (version {version}) not available within {timeout} seconds. Last status: {resp.status_code}, {resp.text}") # type: ignore
        resp.raise_for_status()  # Check for HTTP errors

        assert resp.status_code == 200
        status_data = resp.json()
        assert status_data["job_id"] == job_id
        assert "state" in status_data
        # The state could be QUEUED, ACTIVE, PENDING, or even COMPLETED if it's very short
        assert status_data["state"] in ["NEW", "QUEUED", "ACTIVE", "COMPLETED", "PENDING", "FAILED", "CANCELED"]
        assert isinstance(status_data["details"], dict) # Check details field exists
    finally:
        # Ensure cleanup even if assertions fail
        try:
            requests.delete(f'{BASE_URL}/api/{backend}/{version}/job/{job_id}', headers=headers)
        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to clean up job {job_id} for backend {backend} in test_get_job_status_valid: {e}")


# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_get_job_status_not_found(backend_config):
    """Tests retrieving the status of a job ID that does not exist."""
    backend, version, token = backend_config
    non_existent_job_id = "999999999" # Assumed not to exist
    headers = _get_auth_headers_for_backend(token)
    resp = requests.get(f'{BASE_URL}/api/{backend}/{version}/job/{non_existent_job_id}', headers=headers)
    assert resp.status_code == 404

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_get_job_status_invalid_id_format(backend_config):
    """Tests retrieving status with a non-numeric job ID."""
    backend, version, token = backend_config
    headers = _get_auth_headers_for_backend(token)
    resp = requests.get(f'{BASE_URL}/api/{backend}/{version}/job/invalid-job-id', headers=headers)
    # Expecting 400 based on the validation added in the endpoint
    assert resp.status_code == 400
    assert "Invalid job_id" in resp.json().get("detail", "")

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_get_job_status_invalid_id_zero(backend_config):
    """Tests retrieving status with job ID 0."""
    backend, version, token = backend_config
    headers = _get_auth_headers_for_backend(token)
    resp = requests.get(f'{BASE_URL}/api/{backend}/{version}/job/0', headers=headers)
    assert resp.status_code == 400
    assert "Invalid job_id" in resp.json().get("detail", "")

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_get_job_status_invalid_id_negative(backend_config):
    """Tests retrieving status with a negative job ID."""
    backend, version, token = backend_config
    headers = _get_auth_headers_for_backend(token)
    resp = requests.get(f'{BASE_URL}/api/{backend}/{version}/job/-5', headers=headers)
    assert resp.status_code == 400
    assert "Invalid job_id" in resp.json().get("detail", "")


# --- Tests for Cancel Job ---

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_cancel_job_valid(backend_config):
    """Tests canceling a submitted job."""
    backend, version, token = backend_config
    # Submit a job that runs long enough to be cancelled
    job_id = submit_test_job(backend, version, token, args=["30"], name=f"cancel_test_{backend}_{version}") # Sleep for 30s
    headers = _get_auth_headers_for_backend(token)
    job_id_obtained = True # Flag to track if job_id was obtained
    try:
        resp = requests.delete(f'{BASE_URL}/api/{backend}/{version}/job/{job_id}', headers=headers)
        assert resp.status_code == 204 # No Content on successful deletion

        # Optional: Verify status becomes CANCELED (can be flaky due to timing)
        time.sleep(2) # Give time for cancellation to propagate
        status_resp = requests.get(f'{BASE_URL}/api/{backend}/{version}/job/{job_id}', headers=headers)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            print(f"Job {job_id} status after cancel request: {status_data.get('state')}")
            # Possible states after cancel: CANCELED, COMPLETED (if finished before cancel took effect), FAILED
            assert status_data.get("state") in ["CANCELED", "COMPLETED", "FAILED"]
        elif status_resp.status_code == 404:
             # If the job is cleaned up very quickly after cancellation, 404 is also acceptable
             print(f"Job {job_id} not found after cancel request (potentially cleaned up).")
        else:
             # Raise unexpected status code during status check
             status_resp.raise_for_status()

    except Exception as e:
         # Ensure cleanup attempt even if the test fails mid-way
         print(f"Error during test_cancel_job_valid for backend {backend}: {e}")
         # Attempt cleanup if job_id was obtained
         if 'job_id' in locals() and 'version' in locals():
             try:
                 requests.delete(f'{BASE_URL}/api/{backend}/{version}/job/{job_id}', headers=headers)
             except requests.exceptions.RequestException as ce:
                 print(f"Warning: Failed to clean up job {job_id} for backend {backend} during exception handling: {ce}")
         raise e # Re-raise the original exception


# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_cancel_job_not_found(backend_config):
    """Tests canceling a job ID that does not exist."""
    backend, version, token = backend_config
    non_existent_job_id = "999999998" # Assumed not to exist
    headers = _get_auth_headers_for_backend(token)
    resp = requests.delete(f'{BASE_URL}/api/{backend}/{version}/job/{non_existent_job_id}', headers=headers)
    assert resp.status_code == 404


# --- Test for List Jobs ---

# @pytest.mark.parametrize("backend_config", get_available_backends())
def test_list_jobs(backend_config):
    """Tests listing active jobs."""
    backend, version, token = backend_config
    # Submit a job to ensure there's at least one job to list
    headers = _get_auth_headers_for_backend(token) # Get headers before submitting job
    job_id = submit_test_job(backend, version, token, name=f"list_test_{backend}_{version}")
    try:
        resp = requests.get(f'{BASE_URL}/api/{backend}/{version}/jobs', headers=headers)
        resp.raise_for_status() # Check for HTTP errors

        assert resp.status_code == 200
        job_list = resp.json()
        assert isinstance(job_list, list)
        # Check that all items in the list are strings (job IDs)
        assert all(isinstance(item, str) for item in job_list)
        # Verify the submitted job ID is in the list returned by the API
        assert job_id in job_list
        print(f"Found job {job_id} in list: {job_list}")

    finally:
        # Clean up the submitted job
        try:
            requests.delete(f'{BASE_URL}/api/{backend}/{version}/job/{job_id}', headers=headers)
        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to clean up job {job_id} for backend {backend} in test_list_jobs: {e}")
