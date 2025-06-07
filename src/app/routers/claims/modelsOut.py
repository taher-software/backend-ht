from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict
from src.app.globals.response import ApiResponse
from src.app.routers.users.modelsIn import UserOrm


class ClaimGI(BaseModel):
    id: int = Field(...)
    claim_title: str = Field(...)
    created_at: datetime
    status: str = Field(...)


class ClaimDetails(BaseModel):
    id: int = Field(...)
    guest_id: str = Field(...)
    status: str = Field(...)
    stay_id: int = Field(...)
    claim_text: str | None = Field(None)
    claim_title: str | None = Field(None)
    claim_voice_url: str | None = Field(None)
    claim_voice_duration: float | None = Field(None)
    videoObject: dict | None = Field(None, alias="claim_video_url")
    imagesObject: list | None = Field(None, alias="claim_images_url")
    acknowledged_employee_id: int | None = Field(None)
    acknowledged_claim_time: datetime | None = Field(None)
    resolver_employee_id: int | None = Field(None)
    resolve_claim_time: datetime | None = Field(None)
    approve_claim_time: datetime | None = Field(None)
    reject_claim_time: datetime | None = Field(None)
    claim_language: str = Field(...)

    claim_category: str = Field(...)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)
    namespace_id: int = Field(...)

    receiver: UserOrm | None = Field(None, alias="receiver")
    resolver: UserOrm | None = Field(None, alias="resolver")

    class Config:
        from_attributes = True


class ClaimDetailsResponse(ApiResponse):
    data: ClaimDetails
