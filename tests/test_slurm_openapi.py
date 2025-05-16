import slurmrestd_client
from slurmrestd_client.api import slurm_api
from slurmrestd_client.configuration import Configuration
from slurmrestd_client.models import SlurmV0041GetDiag200Response
from .utils import fetch_slurm_token
import pytest

def test_slurm_service_active():
    # Fetch the SLURM JWT token
    token = fetch_slurm_token()
    if not token:
        pytest.skip("SLURM_JWT token not found, skipping test.")

    # Configure the client
    configuration = Configuration(
        host="http://localhost:9200",
        access_token=token,
        username='root',  # TODO: Username should be set in the environment
        debug=True
    )
    
    # Create an instance of the SlurmApi
    api_client = slurmrestd_client.ApiClient(configuration)
    api_instance = slurm_api.SlurmApi(api_client)
    
    try:
        # Call the diagnostics endpoint
        response: SlurmV0041GetDiag200Response = api_instance.slurm_v0041_get_diag()
        
        # Verify we got a response
        assert response is not None
        # Verify the response contains diagnostics data
        assert hasattr(response, 'statistics')
        
    except Exception as e:
        assert False, f"Failed to connect to Slurm REST API: {str(e)}"
