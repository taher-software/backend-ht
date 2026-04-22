from pydantic import BaseModel
from src.app.globals.enum import JobType


# ------------ Pub/Sub Push Message Format ------------
class PubSubMessage(BaseModel):
    message: dict
    subscription: str


# ------------ Your internal job payload format ------------
class JobPayload(BaseModel):
    job_type: JobType
    namespace_id: int
    job_id: str
    payload: dict = {}


# ------------ Cloud Tasks HTTP Request Payload ------------
class CloudTaskPayload(BaseModel):
    """Cloud Tasks HTTP request payload (direct JSON, no Base64 encoding)"""

    job_type: JobType
    namespace_id: int
    job_id: str
    guest_id: str | None = None  # Optional guest ID for guest-specific tasks
