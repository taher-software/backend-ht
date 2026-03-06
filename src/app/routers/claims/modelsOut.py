from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict
from src.app.globals.response import ApiResponse
from src.app.routers.users.modelsIn import UserOrm
from src.app.routers.stays.modelsIn import StayOrm


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
    videoObject: str | None = Field(None, alias="claim_video_url")
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
    stay: StayOrm | None = Field(None, alias="stay")

    class Config:
        from_attributes = True


class ExtendedClaimDetails(ClaimDetails):
    claim_summary: str | None = Field(None)


class ClaimDetailsResponse(ApiResponse):
    data: ClaimDetails


class GuestOut(BaseModel):
    phone_number: str
    first_name: str
    last_name: str
    avatar_url: str | None = None
    nationality: str
    country_of_residence: str

    class Config:
        from_attributes = True


class RoomOut(BaseModel):
    id: int
    room_number: str
    floor: str | None = None
    room_type: str | None = None

    class Config:
        from_attributes = True


class StayWithRoom(StayOrm):
    room: RoomOut | None = None

    class Config:
        from_attributes = True


class ClaimWithRoom(BaseModel):
    id: int
    guest_id: str
    status: str
    stay_id: int
    claim_text: str | None = None
    claim_title: str | None = None
    claim_voice_url: str | None = None
    claim_voice_duration: float | None = None
    claim_video_url: str | None = None
    claim_images_url: list | None = None
    acknowledged_employee_id: int | None = None
    acknowledged_claim_time: datetime | None = None
    resolver_employee_id: int | None = None
    resolve_claim_time: datetime | None = None
    approve_claim_time: datetime | None = None
    reject_claim_time: datetime | None = None
    claim_language: str
    claim_category: str
    namespace_id: int
    created_at: datetime
    updated_at: datetime
    stay: StayWithRoom | None = None
    guest: GuestOut | None = None

    class Config:
        from_attributes = True
