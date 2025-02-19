import slurmrestd_client
from slurmrestd_client.api import slurm_api
from slurmrestd_client.configuration import Configuration
from slurmrestd_client.models import SlurmV0041GetDiag200Response
import pytest

@pytest.mark.skip(reason="Skipping test as it requires a valid JWT token")
def test_slurm_service_active():
    # Configure the client
    configuration = Configuration(
        host="http://localhost:9200"
        , debug=True
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

