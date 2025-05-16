from enum import Enum
import psij
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from uuid import uuid4

# For now, this is a copy of the Job type from PSI/J. The reason for this duplication is to version # it separately, modify types (callbacks), use Pydantic type-checking. 

class ResourceSpecEx(BaseModel):
    """External resource specification model"""
    node_count: Optional[int] = 1
    process_count: Optional[int] = 1
    processes_per_node: Optional[int] = 1
    cpu_cores_per_process: Optional[int] = 1
    gpu_cores_per_process: Optional[int] = 0
    exclusive_node_use: bool = False


class JobAttributesEx(BaseModel):
    """External job attributes model"""
    duration: Optional[int] = 10  # in minutes
    queue_name: Optional[str] = None
    account: Optional[str] = None
    reservation_id: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None


class JobSpecEx(BaseModel):
    """External job specification model"""
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


class JobStateEx(Enum):
    """External job state enumeration"""
    NEW = "NEW"
    QUEUED = "QUEUED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class JobResponseEx(BaseModel):
    """External job response model"""
    id: str
    state: JobStateEx


class JobStatusEx(BaseModel):
    """External job status model"""
    job_id: str
    state: JobStateEx
    details: Optional[Dict[str, Any]] = None


class JobStateOrderEx:
    """External job state order helper class"""
    @staticmethod
    def prev(state: JobStateEx) -> Optional[JobStateEx]:
        """Returns the previous state in the job state order"""
        order = [JobStateEx.NEW, JobStateEx.QUEUED, JobStateEx.ACTIVE, 
                 JobStateEx.COMPLETED, JobStateEx.FAILED, JobStateEx.CANCELED]
        try:
            idx = order.index(state)
            if idx > 0:
                return order[idx - 1]
            return None
        except ValueError:
            return None


class JobStatusCallbackEx(BaseModel):
    """External job status callback model"""
    callback_url: Optional[HttpUrl] = None
    callback_method: str = "POST"
    headers: Optional[Dict[str, str]] = None


def _generate_id_ex() -> str:
    """Generate a unique ID for a job"""
    return str(uuid4())


class JobEx(BaseModel):
    """External job model that mirrors the PSI/J Job class"""
    id: str = None
    native_id: Optional[str] = None
    status: JobStatusEx = None
    spec: Optional[JobSpecEx] = None
    callback: Optional[JobStatusCallbackEx] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.id = _generate_id_ex()
        if self.status is None:
            self.status = JobStatusEx(job_id=self.id, state=JobStateEx.NEW)


def convert_to_psij_job(job_ex: JobEx) -> 'psij.Job':
    """
    Convert a JobEx (Pydantic model) to a psij Job object.
    
    Args:
        job_ex: The JobEx object to convert.
        
    Returns:
        A fully populated psij Job instance with equivalent data.
    """
    from psij import Job, JobSpec, JobState, JobStatus, ResourceSpecV1, JobAttributes
    
    # Create a new Job instance, possibly with spec
    psij_job_spec = None
    if job_ex.spec:
        # Create JobSpec
        psij_job_spec = JobSpec(
            name=job_ex.spec.name,
            executable=job_ex.spec.executable,
            arguments=job_ex.spec.arguments,
            directory=job_ex.spec.directory,
            inherit_environment=job_ex.spec.inherit_environment,
            environment=job_ex.spec.environment,
            stdin_path=job_ex.spec.stdin_path,
            stdout_path=job_ex.spec.stdout_path,
            stderr_path=job_ex.spec.stderr_path,
            pre_launch=job_ex.spec.pre_launch,
            post_launch=job_ex.spec.post_launch,
            launcher=job_ex.spec.launcher
        )
        
        # Process resources
        if job_ex.spec.resources:
            resources = ResourceSpecV1(
                node_count=job_ex.spec.resources.node_count,
                process_count=job_ex.spec.resources.process_count, 
                processes_per_node=job_ex.spec.resources.processes_per_node,
                cpu_cores_per_process=job_ex.spec.resources.cpu_cores_per_process,
                gpu_cores_per_process=job_ex.spec.resources.gpu_cores_per_process,
                exclusive_node_use=job_ex.spec.resources.exclusive_node_use
            )
            psij_job_spec.resources = resources
            
        # Process attributes - directly pass parameters to JobAttributes
        if job_ex.spec.attributes:
            job_attributes = JobAttributes(
                duration=job_ex.spec.attributes.duration,
                queue_name=job_ex.spec.attributes.queue_name,
                account=job_ex.spec.attributes.account,
                reservation_id=job_ex.spec.attributes.reservation_id,
                custom_attributes=job_ex.spec.attributes.custom_attributes
            )
            psij_job_spec.attributes = job_attributes
    
    # Create the actual Job object
    psij_job = Job(spec=psij_job_spec)
    
    # Set the ID
    # We need to set private attribute directly since id is read-only
    if job_ex.id:
        psij_job._id = job_ex.id
        
    # Set native_id if it exists
    if job_ex.native_id:
        psij_job._native_id = job_ex.native_id
    
    # Set status if it exists
    if job_ex.status:
        # Convert JobStateEx to JobState
        state_mapping = {
            JobStateEx.NEW: JobState.NEW,
            JobStateEx.QUEUED: JobState.QUEUED,
            JobStateEx.ACTIVE: JobState.ACTIVE,
            JobStateEx.COMPLETED: JobState.COMPLETED,
            JobStateEx.FAILED: JobState.FAILED,
            JobStateEx.CANCELED: JobState.CANCELED
        }
        psij_state = state_mapping.get(job_ex.status.state, JobState.NEW)
        psij_job_status = JobStatus(psij_state)
        
        # We need to set the private attribute to avoid triggering callbacks
        psij_job._status = psij_job_status
        
    # TODO: Callback is not converted because psij.Job uses a different callback mechanism
    
    return psij_job


def convert_from_psij_job(psij_job: 'psij.Job') -> JobEx:
    """
    Convert a psij Job object to a JobEx (Pydantic model).
    
    Args:
        psij_job: The psij Job object to convert.
        
    Returns:
        A fully populated JobEx instance with equivalent data.
    """
    from psij import JobState
    
    # Create JobSpecEx if needed
    spec_ex = None
    if psij_job.spec:
        # Convert resources if they exist
        resources_ex = None
        if psij_job.spec.resources:
            resources_ex = ResourceSpecEx(
                node_count=psij_job.spec.resources.node_count,
                process_count=psij_job.spec.resources.process_count,
                processes_per_node=psij_job.spec.resources.processes_per_node,
                cpu_cores_per_process=psij_job.spec.resources.cpu_cores_per_process,
                gpu_cores_per_process=psij_job.spec.resources.gpu_cores_per_process,
                exclusive_node_use=psij_job.spec.resources.exclusive_node_use
            )
        
        # Convert attributes if they exist
        attributes_ex = None
        if psij_job.spec.attributes:
            attrs = psij_job.spec.attributes
            attributes_ex = JobAttributesEx(
                duration=getattr(attrs, 'duration', None),
                queue_name=getattr(attrs, 'queue_name', None),
                account=getattr(attrs, 'account', None),
                reservation_id=getattr(attrs, 'reservation_id', None),
                custom_attributes=getattr(attrs, 'custom_attributes', None)
            )
        
        # Create the JobSpecEx
        spec_ex = JobSpecEx(
            name=psij_job.spec.name,
            executable=psij_job.spec.executable,
            arguments=psij_job.spec.arguments,
            directory=psij_job.spec.directory,
            inherit_environment=psij_job.spec.inherit_environment,
            environment=psij_job.spec.environment,
            stdin_path=psij_job.spec.stdin_path,
            stdout_path=psij_job.spec.stdout_path,
            stderr_path=psij_job.spec.stderr_path,
            resources=resources_ex,
            attributes=attributes_ex,
            pre_launch=psij_job.spec.pre_launch,
            post_launch=psij_job.spec.post_launch,
            launcher=psij_job.spec.launcher
        )
    
    # Convert status
    status_ex = None
    if psij_job.status:
        # Map JobState to JobStateEx
        state_mapping = {
            JobState.NEW: JobStateEx.NEW,
            JobState.QUEUED: JobStateEx.QUEUED, 
            JobState.ACTIVE: JobStateEx.ACTIVE,
            JobState.COMPLETED: JobStateEx.COMPLETED,
            JobState.FAILED: JobStateEx.FAILED,
            JobState.CANCELED: JobStateEx.CANCELED
        }
        state_ex = state_mapping.get(psij_job.status.state, JobStateEx.NEW)
        status_ex = JobStatusEx(
            job_id=psij_job.id,
            state=state_ex,
            # Note: We don't have direct access to details in psij.JobStatus
            details={}
        )
    
    # Create the JobEx
    job_ex = JobEx(
        id=psij_job.id,
        native_id=psij_job.native_id,
        status=status_ex,
        spec=spec_ex,
        # Note: No conversion for callback as psij uses a different mechanism
        callback=None
    )
    
    return job_ex
