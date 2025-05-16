from typing import Optional
from psij import Job, JobExecutor, JobExecutorConfig, JobStatus, JobState, JobSpec, ResourceSpec
from slurmrestd_client.exceptions import ApiException
from slurmrestd_client.api_client import ApiClient
from slurmrestd_client.api.slurm_api import SlurmApi
from slurmrestd_client.configuration import Configuration
from slurmrestd_client.models.slurm_v0041_post_job_submit_request import SlurmV0041PostJobSubmitRequest
from slurmrestd_client.models.slurm_v0041_post_job_submit_request_job import SlurmV0041PostJobSubmitRequestJob
from slurmrestd_client.models.slurm_v0041_post_job_submit_request_jobs_inner_time_limit import SlurmV0041PostJobSubmitRequestJobsInnerTimeLimit
import logging

logger = logging.getLogger(__name__)

class SlurmRestAPIExecutorConfig(JobExecutorConfig):
    """Configuration for the Slurm REST API executor
    
       Note: See slurmrestd_client.Configuration for more configuration options
    """
    def __init__(self, token: str = '', verify_ssl: bool = True):
        super().__init__()
        self.token = token
        self.verify_ssl = verify_ssl


class SlurmRestAPIExecutor(JobExecutor):
    _NAME_ = "Slurm REST API Executor"
    _VERSION_ = "0.0.1"
    _DESCRIPTION_ = "Configuration for the Slurm REST API executor"
    
    def __init__(self, url: Optional[str] = None,
                 config: Optional[SlurmRestAPIExecutorConfig] = None):
        super().__init__(url=url, config=config)
        self.config = config if config else SlurmRestAPIExecutorConfig() # Store config
        # Configure API client
        configuration = Configuration(host=url)
        configuration.verify_ssl = self.config.verify_ssl
        # The token from config is used to initialize the API client's default token
        configuration.api_key['token'] = self.config.token
        
        self.api_client = ApiClient(configuration)
        self.slurm_api = SlurmApi(self.api_client)
        self.log = logging.getLogger(__name__)

    def submit(self, job: Job) -> None:
        """Submit a job to Slurm via REST API"""
        logger.info(f"Submitting job: {job}")
        job_spec: JobSpec = job.spec if job.spec else JobSpec() # TODO: What happens is there's no JobSpec?
        
        # Convert PSI/J job spec to Slurm submission request
        total_minutes = int(job_spec.attributes.duration.total_seconds() // 60)
        node_count = 1
        if job_spec.resources and isinstance(job_spec.resources, ResourceSpec):
            node_count = job_spec.resources.node_count 

        job_request = SlurmV0041PostJobSubmitRequest(
            job=SlurmV0041PostJobSubmitRequestJob(
                nodes=str(node_count),
                # ntasks_per_tres=job_spec.resources.process_count,
                time_limit=SlurmV0041PostJobSubmitRequestJobsInnerTimeLimit(set=True, number=total_minutes),
                current_working_directory=str(job_spec.directory) if job_spec.directory else None,
                environment=[k+'='+v for k,v in job_spec.environment.items()] if job_spec.environment else None,
                name=job_spec.name,
                script=job_spec.executable  # TODO: What should script look like? 
            )
        )
        logger.info(f"Submitting job request: {job_request}")
        try:
            # Pass the SLURM_JWT token as a header
            headers = {'X-SLURM-USER-TOKEN': self.config.token,
                       'X-SLURM-USER-NAME': 'root'} # TODO: Consider making username configurable
            response = self.slurm_api.slurm_v0041_post_job_submit(slurm_v0041_post_job_submit_request=job_request, _headers=headers)
            self.log.info(f"Job submitted: {response.job_id}")
            job._native_id = str(response.job_id)
            job.status = JobStatus(JobState.QUEUED)
        except ApiException as e:
            logger.error(f"Failed to submit job: {str(e)}")
            raise Exception(f"Failed to submit job: {str(e)}")

    def cancel(self, job: Job) -> None:
        """Cancel a running job"""
        if job.native_id:
            try:
                # Pass the SLURM_JWT token as a header
                headers = {'X-SLURM-USER-TOKEN': self.config.token,
                           'X-SLURM-USER-NAME': 'root'} # TODO: Consider making username configurable
                self.slurm_api.slurm_v0040_delete_job(job.native_id, _headers=headers)
                # TODO: Should check this response to make sure it was canceled
                job.status = JobStatus(JobState.CANCELED)
            except ApiException as e:
                raise Exception(f"Failed to cancel job {job.native_id}: {str(e)}")

    def list(self) -> list[str]:
        """List all jobs in the system"""
        try:
            headers = {'X-SLURM-USER-TOKEN': self.config.token,
                       'X-SLURM-USER-NAME': 'root'} # TODO: Consider making username configurable
            response = self.slurm_api.slurm_v0040_get_jobs(_headers=headers)
            jobs = []
            for job_info in response.jobs:
                jobs.append(str(job_info.job_id))
                logging.info(f"Listing job {job_info.job_id}: {str(job_info)}")
            return jobs
        except ApiException as e:
            raise Exception(f"Failed to list jobs: {str(e)}")

    def _update_job_status(self, job: Job) -> None:
        """Update the status of a job"""
        if job.native_id:
            try:
                headers = {'X-SLURM-USER-TOKEN': self.config.token,
                           'X-SLURM-USER-NAME': 'root'} # TODO: Consider making username configurable
                response = self.slurm_api.slurm_v0040_get_job(job.native_id, _headers=headers)
                if response and hasattr(response, 'jobs') and len(response.jobs) > 0:
                    job_info = response.jobs[0]  # Get the first job from the response
                    state = job_info.job_state or ''
                    if state: # Ensure state is not empty
                        # Slurm job_state can be a list of state strings, usually the first one is the primary.
                        # Example: ["PENDING", "JOB_ARRAY_TASK_LIMIT"]
                        # We take the first state for mapping.
                        primary_slurm_state = state[0] if isinstance(state, list) and state else state if isinstance(state, str) else ''
                        job_state = self._map_slurm_state_to_psij(primary_slurm_state)
                        job.status = JobStatus(job_state)
                    else:
                        # If state is empty or not parsable, log and potentially set to a default/unknown state
                        logger.warning(f"Received empty or unparsable state for job {job.native_id}: {job_info.job_state}")
                        # Or, re-raise or handle as an error if appropriate
            except ApiException as e:
                raise Exception(f"Failed to get job status for job {job.native_id}: {str(e)}")
    def _map_slurm_state_to_psij(self, slurm_state: str) -> JobState:
        """Map Slurm job states to PSI/J job states"""
        # TODO: Move this map outside the function. 
        # NEW, QUEUED, ACTIVE, COMPLETED, FAILED, and CANCELED.
        mapping = {
            'PENDING': JobState.QUEUED,
            'CONFIGURING': JobState.NEW,
            'RUNNING': JobState.ACTIVE,
            'COMPLETED': JobState.COMPLETED,
            'CANCELLED': JobState.CANCELED,
            'FAILED': JobState.FAILED,
            'TIMEOUT': JobState.FAILED,
            'PREEMPTED': JobState.FAILED,
            'NODE_FAIL': JobState.FAILED,
            'SUSPENDED': JobState.CANCELED
        }
        ret = mapping.get(slurm_state.upper(), None)
        if not ret:
            raise Exception(f"Invalid job status code: {slurm_state}")
        return ret 

    def attach(self, job: Job, native_id: str) -> None: # Signature matches JobExecutor
        """Attach to an existing job"""
        job._native_id = native_id
        self._update_job_status(job)
