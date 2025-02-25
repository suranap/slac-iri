from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator, model_validator, validator
from typing import Optional, Dict, Any, List
from datetime import timedelta
from psij import Job, JobSpec, JobState, JobExecutor, ResourceSpec, JobAttributes
from psijd.executors.psij_slurmrestd.psij_slurmrestd.slurmrestd import SlurmRestAPIExecutor
from enum import Enum

app = FastAPI(title='PSI/J Service API', version='0.1')

# Classes ending in Ex means External. They should be validated and converted to internal classes.

class ResourceSpecEx(BaseModel):
    node_count: Optional[int] = None
    process_count: Optional[int] = None
    processes_per_node: Optional[int] = None
    cpu_cores_per_process: Optional[int] = None
    gpu_cores_per_process: Optional[int] = None
    exclusive_node_use: bool = False


class JobAttributesEx(BaseModel):
    duration: Optional[timedelta] = None
    queue_name: Optional[str] = None
    account: Optional[str] = None
    reservation_id: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None


# --- JobRequestEx Definition ---

class JobSpecEx(BaseModel):
    name: Optional[str] = None
    script: Optional[str] = None
    executable: Optional[str] = None
    arguments: Optional[List[str]] = None
    directory: Optional[str] = None
    inherit_environment: bool = True
    environment: Optional[Dict[str, str]] = None
    stdin_path: Optional[str] = None
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    resources: Optional[ResourceSpecEx] = None
    attributes: Optional[JobAttributesEx] = None
    pre_launch: Optional[str] = None
    post_launch: Optional[str] = None
    launcher: Optional[str] = None

class JobStateEx(str, Enum):
    NEW = "NEW"
    QUEUED = "QUEUED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class JobResponseEx(BaseModel):
    id: str
    state: JobStateEx

class JobStatusEx(BaseModel):
    job_id: str
    state: JobStateEx
    details: Optional[Dict[str, Any]] = None


# Initialize the executor as a global variable.  SHOULD BE CONFIGURED
# executor = SlurmRestAPIExecutor(url='http://slurmrestd:9200', auth_token='your-auth-token') # Replace with your actual values

# HACK: This needs to be in a database. Track a mapping from external ID to internal Job class.
JOBS_MAP: Dict[str, Job] = {}

@app.post("/jobs", response_model=JobResponseEx, status_code=201)
async def submit_job(job_request: JobSpecEx):
    """Submit a new job to the SLURM cluster"""
    try:
        # --- Convert JobRequestEx to JobSpec ---
        resource_spec_kwargs = {}
        if job_request.resources:
            resource_spec_kwargs.update(job_request.resources.model_dump(mode='python'))
            if job_request.resources.custom_resources:
                resource_spec_kwargs.update(job_request.resources.custom_resources)

        attribute_kwargs = {}
        if job_request.attributes:
            attribute_kwargs.update(job_request.attributes.model_dump(mode='python'))

        job_spec = JobSpec(
            name=job_request.name,
            script=job_request.script,
            executable=job_request.executable,
            arguments=job_request.arguments,
            directory=job_request.directory,
            inherit_environment=job_request.inherit_environment,
            environment=job_request.environment,
            stdin_path=job_request.stdin_path,
            stdout_path=job_request.stdout_path,
            stderr_path=job_request.stderr_path,
            resources=ResourceSpec(**resource_spec_kwargs),
            attributes=JobAttributes(**attribute_kwargs),
            pre_launch=job_request.pre_launch,
            post_launch=job_request.post_launch,
            launcher=job_request.launcher
        )

        job = Job(spec=job_spec)
        executor.submit(job)
        JOBS_MAP[jpb.id] = job
        return JobResponseEx(id=job.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}", response_model=JobStatusEx)
async def get_job_status(job_id: str):
    """Get the status of a specific job"""
    try:
        job = JOBS_MAP.get(job_id, None)
        if not job:
            raise Exception(job_id)
        status = executor.get_status(job)
        return JobStatusEx(
            job_id=job_id,
            state=str(status.state),
            details={
                "exit_code": status.exit_code,
                "message": status.message if status.message else None
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")

@app.delete("/jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str):
    """Cancel a running job"""
    try:
        job = JOBS_MAP.get(job_id, None)
        if not job:
            raise Exception(job_id)
        job.native_id = job_id
        executor.cancel(job)
        return None
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to cancel job: {str(e)}")

@app.get("/jobs", response_model=list[JobStatusEx])
async def list_jobs():
    """List all jobs and their statuses"""
    try:
        jobs = executor.list_jobs()
        return [
            JobStatusEx(
                job_id=job.native_id,
                state=str(executor.get_status(job).state),
                details=None
            ) for job in jobs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
    
@app.get("/health/slurmrestd", response_model=dict)
async def health_check():
    """Health check for the SLURM REST API"""
    try:
        response = requests.get('http://slurmrestd:9200//slurm/v0.0.41/ping')
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/hello", response_model=str)
async def hello():
    return "Hello, world!"
