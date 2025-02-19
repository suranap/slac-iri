import requests
import subprocess
import pytest

BASE_URL = 'http://localhost:9200/'

@pytest.fixture(scope="module")
def jwt_token():
    """Fixture to get JWT token for all tests"""
    result = subprocess.run(
        ['docker', 'compose', '-f', 'slurm/docker-compose.yml', 'exec', 'slurmrestd', 'scontrol', 'token'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Error getting token: {result.stderr}")
    # Extract only the token part after 'SLURM_JWT='
    return result.stdout.strip().split('SLURM_JWT=')[1]

def create_job_specification(
    name="test",
    ntasks=1,
    nodes=1,
    working_dir="/root",
    stdin="/dev/null",
    stdout="/root/test.out",
    stderr="/root/test_error.out",
    script="#!/bin/bash\n echo 'SLURM REST API works'",
    env_path="/bin:/usr/bin/:/usr/local/bin/",
    env_ld_library_path="/lib/:/lib64/:/usr/local/lib"
):
    job_data = {
        "job": {
            "name": name,
            "ntasks": ntasks,
            "nodes": nodes,
            "current_working_directory": working_dir,
            "standard_input": stdin,
            "standard_output": stdout,
            "standard_error": stderr,
            "environment": {
                "PATH": env_path,
                "LD_LIBRARY_PATH": env_ld_library_path
            }
        },
        "script": script
    }
    return job_data

def test_jwt_token_retrieval(jwt_token):
    """Test that we can successfully retrieve a JWT token"""
    assert jwt_token is not None
    assert len(jwt_token) > 0

def test_diagnostic_endpoint(jwt_token):
    """Test the diagnostic endpoint"""
    url = BASE_URL + 'slurm/v0.0.41/diag'
    headers = {
        'X-SLURM-USER-TOKEN': jwt_token,
        'X-SLURM-USER-NAME': 'root'
    }

    response = requests.get(url, headers=headers, verify=False)
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    data = response.json()
    assert 'statistics' in data, "Response should contain statistics"

def test_job_submission(jwt_token):
    """Test job submission through the REST API"""
    job_data = create_job_specification()
    
    url = BASE_URL + 'slurm/v0.0.41/job/submit'
    headers = {
        'X-SLURM-USER-TOKEN': jwt_token,
        'X-SLURM-USER-NAME': 'root',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, headers=headers, json=job_data, verify=False)
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    response_data = response.json()
    assert 'job_id' in response_data, "Response should contain job_id"
    assert isinstance(response_data['job_id'], int), "Job ID should be an integer"
