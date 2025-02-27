import asyncio
from typing import Optional, Dict, Any
from psij import Job, JobExecutor, JobStatus, JobState, JobSpec, JobStatusCallback
import slurmrestd_client
from slurmrestd_client.rest import ApiException
from slurmrestd_client.api.slurm_api import SlurmApi

class SlurmRestAPIExecutor(JobExecutor):
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        super().__init__()
        # Configure API client
        configuration = slurmrestd_client.Configuration(
            host=base_url,
            verify_ssl=verify_ssl
        )
        configuration.api_key['token'] = token
        
        self.api_client = slurmrestd_client.ApiClient(configuration)
        self.slurm_api = SlurmApi(self.api_client)

    def submit(self, job: Job) -> None:
        """Submit a job to Slurm via REST API"""
        job_spec: JobSpec = job.spec
        
        # Convert PSI/J job spec to Slurm submission request
        job_properties = {
            "script": job_spec.script,
            "nodes": job_spec.resources.get('node_count', 1),
            "ntasks": job_spec.resources.get('process_count', 1),
            "time_limit": job_spec.attributes.get('time_limit', '01:00:00'),
            "current_working_directory": job_spec.directory if job_spec.directory else None,
            "environment": job_spec.environment if job_spec.environment else None,
            "name": job_spec.name
        }
        
        try:
            response = self.slurm_api.slurm_v0039_job_submit(json_body=job_properties)
            job._native_id = str(response.job_id)
            job.status = JobStatus(JobState.QUEUED)
        except ApiException as e:
            raise Exception(f"Failed to submit job: {str(e)}")

    def cancel(self, job: Job) -> None:
        """Cancel a running job"""
        if job.native_id:
            try:
                self.slurm_api.slurm_v0039_cancel_job(job_id=job.native_id)
                job.status = JobStatus(JobState.CANCELED)
            except ApiException as e:
                raise Exception(f"Failed to cancel job {job.native_id}: {str(e)}")

    def list_jobs(self) -> list[Job]:
        """List all jobs in the system"""
        try:
            response = self.slurm_api.slurm_v0039_jobs_get()
            jobs = []
            for job_data in response.jobs:
                job = Job()
                job._native_id = str(job_data.job_id)
                job.status = JobStatus(self._map_slurm_state_to_psij(job_data.job_state))
                jobs.append(job)
            return jobs
        except ApiException as e:
            raise Exception(f"Failed to list jobs: {str(e)}")

    def _update_job_status(self, job: Job) -> None:
        """Update the status of a job"""
        if job.native_id:
            try:
                response = self.slurm_api.slurm_v0039_job_get(job_id=job.native_id)
                if response and hasattr(response, 'jobs') and response.jobs:
                    job_info = response.jobs[0]  # Get the first job from the response
                    job_state = self._map_slurm_state_to_psij(job_info.job_state)
                    details = {
                        "exit_code": job_info.exit_code if hasattr(job_info, 'exit_code') else None,
                        "start_time": job_info.start_time if hasattr(job_info, 'start_time') else None,
                        "end_time": job_info.end_time if hasattr(job_info, 'end_time') else None
                    }
                    job.status = JobStatus(job_state, details=details)
            except ApiException as e:
                raise Exception(f"Failed to get job status for {job.native_id}: {str(e)}")

    def _map_slurm_state_to_psij(self, slurm_state: str) -> JobState:
        """Map Slurm job states to PSI/J job states"""
        mapping = {
            'PENDING': JobState.QUEUED,
            'CONFIGURING': JobState.QUEUED,
            'RUNNING': JobState.ACTIVE,
            'COMPLETED': JobState.COMPLETED,
            'CANCELLED': JobState.CANCELED,
            'FAILED': JobState.FAILED,
            'TIMEOUT': JobState.FAILED,
            'PREEMPTED': JobState.FAILED,
            'NODE_FAIL': JobState.FAILED,
            'SUSPENDED': JobState.SUSPENDED
        }
        return mapping.get(slurm_state.upper(), JobState.UNKNOWN)

    def attach(self, job: Job, native_id: str) -> None:
        """Attach to an existing job"""
        job._native_id = native_id
        self._update_job_status(job)

    def get_status(self, job: Job) -> JobStatus:
        """Get the current status of a job"""
        self._update_job_status(job)
        return job.status

    def __del__(self):
        """Cleanup when the executor is destroyed"""
        if hasattr(self, 'api_client'):
            self.api_client.close()