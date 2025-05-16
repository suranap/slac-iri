from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List
from psij import Job, JobSpec, JobState, JobAttributes, ResourceSpecV1
import logging
import os

from psijd.service.models import JobEx, JobSpecEx, JobStateEx, JobResponseEx, JobStatusEx, convert_to_psij_job
from psijd.service.backend import get_executor
from psijd.service.auth_utils import get_bearer_token

router = APIRouter()
logger = logging.getLogger(__name__)

# Backend and version constants
BACKEND = 'nersc'
VERSION = 'v0.1.0'

def get_nersc_executor_with_token(access_token: str = Depends(get_bearer_token)):
    """Get NERSC executor for this version, configured with the access token."""
    return get_executor(BACKEND, VERSION, access_token=access_token)

@router.post("/job", response_model=JobResponseEx, status_code=201)
async def submit_job(
    job_request: JobEx,
    executor=Depends(get_nersc_executor_with_token)
):
    """Submit a new job to NERSC (v0.1.0)"""
    logger.info(f"Received job request for {BACKEND} {VERSION}: {job_request}")

    try:
        # Convert JobEx to Job
        job = convert_to_psij_job(job_request)
        logger.info(f"Created job: {job}")
        executor.submit(job)
        if not job._native_id:
            logger.error(f"Job submission to {BACKEND} {VERSION} did not return a native ID.")
            raise HTTPException(status_code=500, detail="Job submitted but no native ID was returned by the executor.")
        logger.info(f"Job submitted with native ID: {job._native_id}")
        return JobResponseEx(id=str(job._native_id), state=JobStateEx.QUEUED)
    except Exception as e:
        logger.error(f"Error submitting job to {BACKEND} {VERSION}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job/{job_id}", response_model=JobStatusEx)
async def get_job_status(
    job_id: str,
    executor=Depends(get_nersc_executor_with_token)
):
    """Get the status of a specific job using the native job id"""
    if not job_id.isdigit() or int(job_id) <= 0:
        raise HTTPException(status_code=400, detail="Invalid job_id. It must be an integer greater than 0.")

    jobspec = JobSpec()
    job = Job(spec=jobspec)
    try:
        executor.attach(job, job_id)
        return JobStatusEx(
            job_id=job_id,
            state=JobStateEx(str(job.status.state)),
            details={}  # TODO: Add more details if needed
        )
    except Exception as e: 
        logger.error(f"Error getting status for job {job_id} from {BACKEND} {VERSION}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")

@router.delete("/job/{job_id}", status_code=204)
async def cancel_job(
    job_id: str,
    executor=Depends(get_nersc_executor_with_token)
):
    """Cancel a running job"""
    try:
        job = Job()
        job._native_id = job_id
        executor.cancel(job)
        return None
    except Exception as e:
        logger.error(f"Error cancelling job {job_id} on {BACKEND} {VERSION}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Failed to cancel job: {str(e)}")

@router.get("/jobs", response_model=List[str])
async def list_jobs(
    access_token: str = Depends(get_bearer_token),
    executor=Depends(get_nersc_executor_with_token)
):
    """List all active job ids"""
    try:
        jobs = executor.list()
        return jobs 
    except Exception as e:
        logger.error(f"Error listing jobs from {BACKEND} {VERSION}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
    
@router.get("/health", response_model=dict)
async def health_check():
    """Health check for the NERSC backend (v0.1.0)"""
    # For health check, instantiate executor without a specific user token
    executor = get_executor(BACKEND, VERSION, access_token=None)
    try:
        return {
            "status": "healthy",
            "backend": BACKEND,
            "version": VERSION,
            "executor": executor._NAME_,
            "executor_version": executor._VERSION_
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))