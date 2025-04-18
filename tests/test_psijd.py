import pytest
import os
import requests
import time # Added for delays

# Define the base URL for the service
BASE_URL = 'http://127.0.0.1:10050'

# --- Helper Function to Submit a Job ---
# This helps reduce code duplication in tests that need a job ID.
def submit_test_job(executable="/usr/bin/sleep", args=["600"], name="api_test"):
    """Submits a simple job and returns its ID."""
    job_spec = {
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
    resp = requests.post(f'{BASE_URL}/job', json=job_spec)
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

# --- Existing Tests ---

def test_hello():
    resp = requests.get(f'{BASE_URL}/hello')
    assert resp.status_code == 200
    assert resp.text == '"Hello, world!"'

def test_health_slurmrestd():
    resp = requests.get(f'{BASE_URL}/health/slurmrestd')
    # Check if the response status code is 200 (or handle potential errors like 503 if slurmrestd is down)
    if resp.status_code == 503 or resp.status_code == 504:
         pytest.skip(f"SLURM REST API health check failed: {resp.status_code} - {resp.text}")
    elif resp.status_code != 200:
         # Print details if it's another unexpected error
         print(f"Unexpected health check status: {resp.status_code}")
         print(f"Response body: {resp.text}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)

def test_submit_job():
    # Use the helper function for consistency
    job_id = submit_test_job(name="submit_job_test")
    assert isinstance(job_id, str)
    # Optional: Clean up the job
    try:
        requests.delete(f'{BASE_URL}/job/{job_id}')
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to clean up job {job_id} in test_submit_job: {e}")


# --- Tests for Get Job Status ---

def test_get_job_status_valid():
    """Tests retrieving the status of a successfully submitted job."""
    job_id = submit_test_job(name="status_test")
    try:
        # Poll the job status until it's available or timeout occurs
        timeout = 10  # seconds
        interval = 1  # seconds
        elapsed = 0
        while elapsed < timeout:
            resp = requests.get(f'{BASE_URL}/job/{job_id}')
            if resp.status_code == 200:
                break
            time.sleep(interval)
            elapsed += interval
        else:
            pytest.fail(f"Job status not available within {timeout} seconds")
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
            requests.delete(f'{BASE_URL}/job/{job_id}')
        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to clean up job {job_id} in test_get_job_status_valid: {e}")


def test_get_job_status_not_found():
    """Tests retrieving the status of a job ID that does not exist."""
    non_existent_job_id = "999999999" # Assumed not to exist
    resp = requests.get(f'{BASE_URL}/job/{non_existent_job_id}')
    assert resp.status_code == 404

def test_get_job_status_invalid_id_format():
    """Tests retrieving status with a non-numeric job ID."""
    resp = requests.get(f'{BASE_URL}/job/invalid-job-id')
    # Expecting 400 based on the validation added in the endpoint
    assert resp.status_code == 400
    assert "Invalid job_id" in resp.json().get("detail", "")

def test_get_job_status_invalid_id_zero():
    """Tests retrieving status with job ID 0."""
    resp = requests.get(f'{BASE_URL}/job/0')
    assert resp.status_code == 400
    assert "Invalid job_id" in resp.json().get("detail", "")

def test_get_job_status_invalid_id_negative():
    """Tests retrieving status with a negative job ID."""
    resp = requests.get(f'{BASE_URL}/job/-5')
    assert resp.status_code == 400
    assert "Invalid job_id" in resp.json().get("detail", "")


# --- Tests for Cancel Job ---

def test_cancel_job_valid():
    """Tests canceling a submitted job."""
    # Submit a job that runs long enough to be cancelled
    job_id = submit_test_job(args=["30"], name="cancel_test") # Sleep for 30s
    try:
        resp = requests.delete(f'{BASE_URL}/job/{job_id}')
        assert resp.status_code == 204 # No Content on successful deletion

        # Optional: Verify status becomes CANCELED (can be flaky due to timing)
        time.sleep(2) # Give time for cancellation to propagate
        status_resp = requests.get(f'{BASE_URL}/job/{job_id}')
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
         print(f"Error during test_cancel_job_valid: {e}")
         # Attempt cleanup if job_id was obtained
         if 'job_id' in locals():
             try:
                 requests.delete(f'{BASE_URL}/job/{job_id}')
             except requests.exceptions.RequestException as ce:
                 print(f"Warning: Failed to clean up job {job_id} during exception handling: {ce}")
         raise e # Re-raise the original exception


def test_cancel_job_not_found():
    """Tests canceling a job ID that does not exist."""
    non_existent_job_id = "999999998" # Assumed not to exist
    resp = requests.delete(f'{BASE_URL}/job/{non_existent_job_id}')
    assert resp.status_code == 404


# --- Test for List Jobs ---

def test_list_jobs():
    """Tests listing active jobs."""
    # Submit a job to ensure there's at least one job to list
    job_id = submit_test_job(name="list_test")
    try:
        resp = requests.get(f'{BASE_URL}/jobs')
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
            requests.delete(f'{BASE_URL}/job/{job_id}')
        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to clean up job {job_id} in test_list_jobs: {e}")

