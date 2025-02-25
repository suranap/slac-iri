import asyncio
from psij import Job, JobExecutor, JobStatus, JobState, JobSpec, JobStatusResponse
from ...nersc.nersc_super_facility_api_client.client import AuthenticatedClient
from ...nersc.nersc_super_facility_api_client.api.compute import submit_job_compute_jobs_machine_post
from ...nersc.nersc_super_facility_api_client.api.tasks import read_task_tasks_id_get, cancel_task_tasks_id_delete
from ...nersc.nersc_super_facility_api_client.models import BodySubmitJobComputeJobsMachinePost, PublicHost

class SuperfacilityAPIExecutor(JobExecutor):
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        super().__init__()
        self.client = AuthenticatedClient(
            base_url=base_url,
            token=token,
            verify_ssl=verify_ssl,
        )

    def submit(self, job: Job) -> None:
        job_spec: JobSpec = job.spec
        job_request = BodySubmitJobComputeJobsMachinePost(
            job=job_spec.script,
            is_path=False
        )
        response = submit_job_compute_jobs_machine_post.sync(
            machine=PublicHost.PERLMUTTER,  # or appropriate machine enum value
            client=self.client,
            body=job_request
        )
        job_id = response.job_id
        job._native_id = job_id
        job.status = JobStatus(JobState.QUEUED)

    def submit(self, job: Job) -> None:
        job_spec: JobSpec = job.spec
        job_request = BodySubmitJobComputeJobsMachinePost(
            job=job_spec.script,
            is_path=False
        )
        response = submit_job_compute_jobs_machine_post.sync(
            machine=PublicHost.PERLMUTTER,
            client=self.client, 
            body=job_request
        )
        job_id = response.job_id
        job._native_id = job_id
        job.status = JobStatus(JobState.QUEUED)

    def cancel(self, job: Job) -> None:
        if job.native_id:
            cancel_task_tasks_id_delete.sync(
                id=job.native_id,
                client=self.client,
                signal=None
            )
            job.status = JobStatus(JobState.CANCELED)

    def list(self) -> None:
        # Implement listing jobs if needed
        pass

    async def _update_job_status(self, job: Job) -> None:
        if job.native_id:
            # Stub function for getting job status
            response: JobStatusResponse = await read_task_tasks_id_get.asyncio(client=self.client, job_id=job.native_id)
            job_state = self._map_superfacility_state_to_psij(response.state)
            job.status = JobStatus(job_state)

    def _map_superfacility_state_to_psij(self, superfacility_state: str) -> JobState:
        mapping = {
            'PENDING': JobState.QUEUED,
            'RUNNING': JobState.ACTIVE,
            'COMPLETED': JobState.COMPLETED,
            'FAILED': JobState.FAILED,
            'CANCELLED': JobState.CANCELED,
            # Add other necessary state mappings
        }
        return mapping.get(superfacility_state, JobState.UNKNOWN)

    def attach(self, job: Job, native_id: str) -> None:
        job._native_id = native_id
        asyncio.run(self._update_job_status(job))

    def describe(self, job: Job) -> None:
        asyncio.run(self._update_job_status(job))