from pydantic import BaseModel, Field
from src.app.globals.response import ApiResponse
from src.app.globals.status import Status
from src.app.globals.error import Error
from typing import Any
from fastapi import status


# Error definitions
claim_not_found_error = Error(
    type="chat", message="Claim not found with the provided ID"
)

guest_not_found_error = Error(
    type="chat", message="Guest associated with claim not found"
)

namespace_mismatch_error = Error(
    type="chat", message="User does not belong to the same namespace as the claim"
)

stay_not_found_error = Error(type="chat", message="Active stay not found for guest")

invalid_stay_dates_error = Error(
    type="chat", message="Guest's stay dates do not include today"
)

stay_namespace_mismatch_error = Error(
    type="chat", message="Stay namespace does not match claim namespace"
)

no_device_token_error = Error(
    type="chat", message="Guest has no device token registered for push notifications"
)

notification_failed_error = Error(
    type="chat", message="Failed to send push notification to guest"
)


# Error response models
class ClaimNotFoundModel(ApiResponse):
    status: Status = Status.failed
    error: Error = claim_not_found_error


class GuestNotFoundModel(ApiResponse):
    status: Status = Status.failed
    error: Error = guest_not_found_error


class NamespaceMismatchModel(ApiResponse):
    status: Status = Status.failed
    error: Error = namespace_mismatch_error


class StayNotFoundModel(ApiResponse):
    status: Status = Status.failed
    error: Error = stay_not_found_error


class InvalidStayDatesModel(ApiResponse):
    status: Status = Status.failed
    error: Error = invalid_stay_dates_error


class StayNamespaceMismatchModel(ApiResponse):
    status: Status = Status.failed
    error: Error = stay_namespace_mismatch_error


class NoDeviceTokenModel(ApiResponse):
    status: Status = Status.failed
    error: Error = no_device_token_error


class NotificationFailedModel(ApiResponse):
    status: Status = Status.failed
    error: Error = notification_failed_error


# Response dictionaries
claim_not_found_response: dict[int, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ClaimNotFoundModel,
        "description": "Claim not found",
    }
}

guest_not_found_response: dict[int, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": GuestNotFoundModel,
        "description": "Guest not found",
    }
}

namespace_mismatch_response: dict[int, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {
        "model": NamespaceMismatchModel,
        "description": "Namespace mismatch",
    }
}

stay_not_found_response: dict[int, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": StayNotFoundModel,
        "description": "Active stay not found",
    }
}

invalid_stay_dates_response: dict[int, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": InvalidStayDatesModel,
        "description": "Invalid stay dates",
    }
}

stay_namespace_mismatch_response: dict[int, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": StayNamespaceMismatchModel,
        "description": "Stay namespace mismatch",
    }
}

no_device_token_response: dict[int, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": NoDeviceTokenModel,
        "description": "No device token",
    }
}

notification_failed_response: dict[int, dict[str, Any]] = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": NotificationFailedModel,
        "description": "Notification failed",
    }
}


# Response models for chat rooms listing
class RoomOut(BaseModel):
    id: int
    namespace_id: int
    room_number: str

    class Config:
        from_attributes = True


class StayOut(BaseModel):
    id: int
    namespace_id: int
    start_date: Any
    end_date: Any
    guest_id: str
    meal_plan: str | None
    room_id: int
    room: RoomOut

    class Config:
        from_attributes = True


class ClaimOut(BaseModel):
    id: int
    status: str
    claim_title: str | None
    claim_text: str | None
    claim_category: str
    created_at: Any

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    avatar_url: str | None
    pref_language: str | None

    class Config:
        from_attributes = True


class GuestOut(BaseModel):
    phone_number: str
    first_name: str
    last_name: str
    avatar_url: str | None
    pref_language: str | None

    class Config:
        from_attributes = True


# Response model for chat messages
class MessageOut(BaseModel):
    id: int
    room_id: int
    namespace_id: int
    owner_type: str
    message_type: str
    seen: bool
    guest_text_version: str | None
    user_text_version: str | None
    guest_voice_url: str | None
    user_voice_url: str | None
    duration: float | None
    image_url: str | None
    video_url: str | None
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class ChatRoomOut(BaseModel):
    id: int
    user_id: int
    guest_id: str
    claim_id: int
    stay_id: int
    namespace_id: int
    active: bool
    created_at: Any
    updated_at: Any
    stay: StayOut
    claim: ClaimOut
    messages: list[MessageOut]
    user: UserOut
    guest: GuestOut

    class Config:
        from_attributes = True
