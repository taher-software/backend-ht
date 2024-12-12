from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict
from app.globals.response import ApiResponse


class ClaimGI(BaseModel):
    id: int = Field(...)
    claim_title: str = Field(...)
    created_at: datetime
    status: str = Field(...)


class ClaimDetails(BaseModel):
    claim_category: str = Field(...)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)
    status: str = Field(...)
    claim_voice_url: str | None = Field(None)
    claim_voice_duration: float | None = Field(None)
    videoObject: dict | None = Field(None, alias="claim_video_url")
    imagesObject: list | None = Field(None, alias="claim_images_url")
    claim_text: str | None = Field(None)


class ClaimDetailsResponse(ApiResponse):
    data: ClaimDetails
