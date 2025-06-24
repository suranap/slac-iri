from typing import Optional, List
import logging
import requests
from pathlib import Path
import inspect
import io
from psij import Job, JobExecutor, JobExecutorConfig, JobStatus, JobState, JobSpec, ResourceSpec
from psij.executors.batch.script_generator import TemplatedScriptGenerator
from sfapi_client import Client
from sfapi_client.compute import Machine

logger = logging.getLogger(__name__)

class NERSCExecutorConfig(JobExecutorConfig):
    """Configuration for the NERSC executor
    
    Args:
        api_key: API key for NERSC authentication
        project: NERSC project account
        token: Optional access token for API calls (e.g., JWT)
    """
    def __init__(self, client_id: str = '', client_private_key: str = '', token: str = ''):
        super().__init__()
        self.client_id = client_id
        self.client_private_key = client_private_key # TODO: This might be used to *fetch* a token if needed
        self.token = token # Store the access token


class NERSCExecutor(JobExecutor):
    _NAME_ = "NERSC Executor"
    _VERSION_ = "0.1.0"
    _DESCRIPTION_ = "Executor for the NERSC computing facility"
    
    def __init__(self, url: Optional[str] = None,
                 config: Optional[NERSCExecutorConfig] = None):
        super().__init__(config=config)
        self.config = config if config else NERSCExecutorConfig()
        self.url = url if url else "https://api.nersc.gov/api/v1.2"
        self.log = logging.getLogger(__name__)
        path_to_template = Path(inspect.getfile(TemplatedScriptGenerator)).parent  / 'slurm' / 'slurm.mustache'
        self.generator = TemplatedScriptGenerator(self.config, path_to_template) # TODO: Generator config might need token/project

    def status(self):
        """Hit the /status endpoint to get general information about NERSC facilities."""
        url = "https://api.nersc.gov/api/v1.2/status"
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        return response

    def submit(self, job: Job) -> None: # Signature matches JobExecutor
        """Submit a job to NERSC"""
        self.log.info(f"Submitting job to NERSC: {job}")
        url = "https://api.nersc.gov/api/v1.2/compute/jobs/perlmutter"

        self._check_job(job)

        # TODO: Convert job into bash script, then send to NERSC

        # Define your variables
        job_path = "/home/suranap/hostname.sh"
        callback_email = "suranap@stanford.edu"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.config.token}", # Use token from config
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "isPath": "true",
            "job": job_path,
            "args": "",
            "callbackTimeout": "0",
            "callbackEmail": callback_email,
            "callbackUrl": "string"
        }

        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()  # Raise an exception for HTTP error codes

        # IMPORTANT: Extract the native job ID from the NERSC API response
        # This is a placeholder, adjust based on the actual NERSC API response structure
        response_data = response.json()
        job._native_id = response_data.get("jobid") # Example key, verify with NERSC docs
        self.log.info(f"Job submitted to NERSC, received native_id: {job._native_id}")

        # Convert PSI/J job spec to Slurm script
        #   Definition of context is in :class:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor`
        # from psij.executors.batch.batch_scheduler_executor import _attrs_to_mustache, _env_to_mustache
        # from psij.executors.batch.template_function_library import ALL as FUNCTION_LIBRARY
        # ctx = {
        #     'job': job,
        #     'custom_attributes': _attrs_to_mustache(job),
        #     'env': _env_to_mustache(job),
        #     'psij': {
        #         'lib': FUNCTION_LIBRARY,
        #         'launch_command': launch_command,
        #         'script_dir': str(self.work_directory)
        #     }
        # }


        # output = io.StringIO()
        # script = self.generator.generate_submit_script(job, context, output)

        # with Client(self.config.client_id, self.config.client_private_key) as client:
        #     perlmutter = client.compute(Machine.perlmutter)
        #     job_ptr = perlmutter.submit_job('') # TODO: Submit batch script

        # try:
        #     # Submit job to NERSC API
        #     response = requests.post(
        #         f"{self.url}/jobs",
        #         json=payload,
        #         headers=self.headers
        #     )
        #     response.raise_for_status()
            
        #     # Parse response and update job
        #     result = response.json()
        #     job._native_id = str(result.get("jobId"))
        #     job.status = JobStatus(JobState.QUEUED)
        #     self.log.info(f"Job submitted to NERSC with ID: {job._native_id}")
        # except requests.exceptions.RequestException as e:
        #     self.log.error(f"Failed to submit job to NERSC: {str(e)}")
        #     if hasattr(e, "response") and e.response:
        #         self.log.error(f"Response: {e.response.text}")
        #     raise Exception(f"Failed to submit job: {str(e)}")

    def cancel(self, job: Job, access_token: str) -> None:
        """Cancel a job on NERSC"""
        if not job.native_id:
            self.log.error("Attempted to cancel a job without a native_id.")
            raise Exception("Job ID is required for cancellation")

        job_id = job.native_id
        url = f"https://api.nersc.gov/api/v1.2/compute/jobs/perlmutter/{job_id}"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.config.token}" # Use token from config
        }
        self.log.info(f"Cancelling job {job_id} on NERSC.")
        response = requests.delete(url, headers=headers)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        self.log.info(f"Job {job_id} cancellation request sent.")

    def list(self, access_token: str) -> List[str]:
        """List all jobs on NERSC"""
        url = "https://api.nersc.gov/api/v1.2/compute/jobs/perlmutter?index=0&sacct=false&cached=true"

        # Define your query parameters in a dictionary
        params = {
            "index": 0,
            "sacct": "false",
            "cached": "true"
        }
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.config.token}" # Use token from config
        }
        self.log.info("Listing jobs on NERSC.")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Assuming the response is a list of job objects, and each has a 'jobid'
        # Adjust based on the actual NERSC API response structure
        job_data_list = response.json()
        job_ids = [str(job_info.get("jobid")) for job_info in job_data_list if job_info.get("jobid")]
        self.log.info(f"Found {len(job_ids)} jobs: {job_ids}")
        return job_ids

        # try:
        #     response = requests.get(
        #         f"{self.url}/jobs",
        #         headers=self.headers,
        #         params={"project": self.config.project}
        #     )
        #     response.raise_for_status()
        #     result = response.json()
            
        #     jobs = []
        #     if "jobs" in result and isinstance(result["jobs"], list):
        #         for job_info in result["jobs"]:
        #             jobs.append(str(job_info.get("jobId")))
        #             self.log.info(f"Found NERSC job {job_info.get('jobId')}")
        #     return jobs
        # except requests.exceptions.RequestException as e:
        #     self.log.error(f"Failed to list jobs on NERSC: {str(e)}")
        #     raise Exception(f"Failed to list jobs: {str(e)}")

    def _update_job_status(self, job: Job) -> None: # Internal method, signature changed
        """Update the status of a job"""
        if not job.native_id:
            self.log.error("Attempted to update status for a job without a native_id.")
            raise Exception("Job ID is required to check status")
            
        try:
            url = f"{self.url}/jobs/{job.native_id}" # Assuming a /jobs/{id} endpoint for status
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {self.config.token}" # Use token from config
            }
            response = requests.get(
                url, headers=headers
            )
            response.raise_for_status()
            job_info = response.json()
            
            # Map NERSC state to PSI/J state
            nersc_state = job_info.get("status", "UNKNOWN")
            job_state = self._map_nersc_state_to_psij(nersc_state)
            job.status = JobStatus(job_state)
            self.log.info(f"Updated status for job {job.native_id}: {job_state}")
        except requests.exceptions.RequestException as e:
            self.log.error(f"Failed to get job status from NERSC: {str(e)}")
            raise Exception(f"Failed to get job status for job {job.native_id}: {str(e)}")

    def _map_nersc_state_to_psij(self, nersc_state: str) -> JobState:
        """Map NERSC job states to PSI/J job states"""
        # Map NERSC states to PSI/J states
        # (this is a simplified mapping - actual mapping may vary)
        mapping = {
            "PENDING": JobState.QUEUED,
            "RUNNING": JobState.ACTIVE,
            "COMPLETED": JobState.COMPLETED,
            "CANCELLED": JobState.CANCELED,
            "FAILED": JobState.FAILED,
            "TIMEOUT": JobState.FAILED,
            "PREEMPTED": JobState.FAILED,
            "NODE_FAIL": JobState.FAILED,
            "SUSPENDED": JobState.QUEUED
        }
        return mapping.get(nersc_state.upper(), JobState.NEW)

    def attach(self, job: Job, native_id: str) -> None: # Signature matches JobExecutor
        """Attach to an existing job on NERSC"""
        job._native_id = native_id
        self._update_job_status(job) # Call internal method without token parameter
