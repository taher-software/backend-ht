from pydantic import BaseModel
from src.app.globals.response import ApiResponse
from src.app.globals.status import Status
from typing import Any
from fastapi import status
from src.app.globals.status import Status
from src.app.globals.error import Error
from src.app.globals.schema_models import GuestModel
from pydantic import Field


class MessageResponse(ApiResponse):
    data: str


no_domain_error = Error(type="auth", message="no_domain_associated_to_user")

no_user_error = Error(type="auth", message="no_user_associated_to_phone_number")

hotel_exist_error = Error(type="auth", message="Hotel already registred!")


class NoDomainModel(ApiResponse):
    status: Status = Status.failed
    error: Error = no_domain_error


class NoGuestModel(ApiResponse):
    status: Status = Status.failed
    error: Error = no_user_error


class HotelEXistModel(ApiResponse):
    status: Status = Status.failed
    error: Error = hotel_exist_error


no_guest_response: dict[int, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": NoGuestModel,
        "description": "No guest with the given phone number",
    }
}

no_domain_response: dict[int, dict[str, Any]] = {
    status.HTTP_417_EXPECTATION_FAILED: {
        "model": NoDomainModel,
        "description": "User not associated to any namespace",
    }
}

hotel_existe_response: dict[int, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": HotelEXistModel,
        "description": "Hotel Already Exist",
    }
}


class AppUser(BaseModel):
    phone_number: str = Field(..., pattern="^\+?[1-9]\d{1,14}$")
    first_name: str = Field(...)
    last_name: str = Field(...)
    avatar_url: str = Field(...)
    devices: list | None = Field(None)


class GuestLogin(BaseModel):
    token: str = Field(...)


class GuestLoginResponse(ApiResponse):
    data: GuestLogin


class OtpModel(BaseModel):
    otp: int = Field(..., le=9999, ge=1000)


class OtpResponse(ApiResponse):
    data: OtpModel


class StayModel(BaseModel):
    stay: bool = Field(...)
    fullname: str = Field(...)
    hotel_name: str | None = Field(None)
    country: str | None = Field(None)
    city: str | None = Field(None)
    avatar: str = Field(...)
    hotel_name: str | None = Field(None)
    claim_count: int | None = Field(None)
    survey_count: int | None = Field(None)
    menu_count: int | None = Field(None)


class MeResponse(ApiResponse):
    data: StayModel
