import logging
import logging.config
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from psij import Job, JobSpec, JobState, JobExecutor, JobAttributes, ResourceSpecV1
from psijd.executors.psij_slurmrestd.psij_slurmrestd.slurmrestd import SlurmRestAPIExecutor, SlurmRestAPIExecutorConfig
from enum import Enum
import os
import requests
 
# Load logging configuration from YAML file
with open("./psijd/logging.yaml", "r") as f:
    config = yaml.safe_load(f)
    logging.config.dictConfig(config)

# Get the logger for this module
logger = logging.getLogger(__name__)  # Use the name defined in logging.yaml

app = FastAPI(title='PSI/J Service API', version='0.1')

# Classes ending in Ex means External. They should be validated and converted to internal classes.

class ResourceSpecEx(BaseModel):
    node_count: Optional[int] = 1
    process_count: Optional[int] = 1
    processes_per_node: Optional[int] = 1
    cpu_cores_per_process: Optional[int] = 1
    gpu_cores_per_process: Optional[int] = 0
    exclusive_node_use: bool = False


class JobAttributesEx(BaseModel):
    duration: Optional[int] = 10
    queue_name: Optional[str] = None
    account: Optional[str] = None
    reservation_id: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None


# --- JobRequestEx Definition ---

class JobSpecEx(BaseModel):
    name: Optional[str] = None
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


# TODO: This should be replaced with proper authentication.
SLURM_JWT = os.getenv('SLURM_JWT') or 'invalid token'


def get_executor(name: str) -> JobExecutor:
    executor = SlurmRestAPIExecutor(url='http://slurmrestd:9200', config=SlurmRestAPIExecutorConfig(token=SLURM_JWT, verify_ssl=False))
    return executor

@app.post("/job", response_model=JobResponseEx, status_code=201)
async def submit_job(job_request: JobSpecEx):
    """Submit a new job to the SLURM cluster"""
    logger.info(f"Received job request: {job_request}")
    try:
        # --- Convert JobRequestEx to JobSpec ---
        resource_spec_kwargs = {}
        if job_request.resources:
            resource_spec_kwargs.update(job_request.resources.model_dump(mode='python'))

        attribute_kwargs = {}
        if job_request.attributes:
            attribute_kwargs.update(job_request.attributes.model_dump(mode='python'))

        job_spec = JobSpec(
            name=job_request.name,
            executable=job_request.executable,
            arguments=job_request.arguments,
            directory=job_request.directory,
            inherit_environment=job_request.inherit_environment,
            environment=job_request.environment,
            stdin_path=job_request.stdin_path,
            stdout_path=job_request.stdout_path,
            stderr_path=job_request.stderr_path,
            resources=ResourceSpecV1(**resource_spec_kwargs),
            attributes=JobAttributes(**attribute_kwargs),
            pre_launch=job_request.pre_launch,
            post_launch=job_request.post_launch,
            launcher=job_request.launcher
        )
        logger.info(f"Converted job request to JobSpec: {job_spec}")
        job = Job(spec=job_spec)
        logger.info(f"Created job: {job}")
        executor = get_executor('slurm')
        logger.info(f"Created executor: {executor}")
        executor.submit(job)
        logger.info(f"Job submitted: {job.id}")
        # TODO: Should the job.id be the internal id or the native id? Native id exposes implementation detail. Id requires storing mapping to native id.
        return JobResponseEx(id=str(job._native_id), state=JobStateEx.QUEUED)
    except Exception as e:
        logger.error(f"Error submitting job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/job/{job_id}", response_model=JobStatusEx)
async def get_job_status(job_id: str):
    """Get the status of a specific job using the native job id"""
    executor = get_executor('slurm') 
    if not job_id.isdigit() or int(job_id) <= 0:
        raise HTTPException(status_code=400, detail="Invalid job_id. It must be an integer greater than 0.")
    jobspec = JobSpec()
    job = Job(spec=jobspec)
    try:
        executor.attach(job, job_id)
        return JobStatusEx(
            job_id=job_id,
            state=JobStateEx(str(job.status.state)),
            details={}          # TODO: Copy relevant info here
        )
    except Exception as e: 
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")

@app.delete("/job/{job_id}", status_code=204)
async def cancel_job(job_id: str):
    """Cancel a running job"""
    try:
        job = Job()
        if not job:
            raise Exception(job_id)
        job._native_id = job_id
        executor = get_executor('slurm')
        executor.cancel(job)
        return None
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to cancel job: {str(e)}")

@app.get("/jobs", response_model=list[str])
async def list_jobs():
    """List all active job ids"""
    try:
        executor = get_executor('slurm')
        jobs = executor.list()
        return jobs 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
    
@app.get("/health/slurmrestd", response_model=dict)
async def health_check():
    """Health check for the SLURM REST API"""
    if not SLURM_JWT:
        raise HTTPException(status_code=400, detail="SLURM_JWT environment variable is not set")

    try:
        headers = {'X-SLURM-USER-TOKEN': SLURM_JWT, 'X-SLURM-USER-NAME': 'root'}
        # Add timeout to prevent hanging requests
        response = requests.get(
            'http://slurmrestd:9200/slurm/v0.0.41/diag', 
            headers=headers,
            timeout=10
        )
        # Print response details for debugging
        print(f"SLURM health check response: Status={response.status_code}, Content={response.text[:100]}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Timeout connecting to SLURM REST API")
    except requests.exceptions.ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Connection error to SLURM REST API: {str(e)}")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from SLURM REST API: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request error to SLURM REST API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/hello", response_model=str)
async def hello():
    return "Hello, world!"
