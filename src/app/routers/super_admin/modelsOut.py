from pydantic import BaseModel
from src.app.globals.response import ApiResponse
from src.app.globals.status import Status
from src.app.globals.error import Error
from typing import Any
from fastapi import status


# Error definitions
namespace_not_found_error = Error(
    type="super_admin", message="Namespace not found with the provided details"
)

user_not_found_error = Error(
    type="super_admin", message="User not found with the provided email"
)

user_namespace_mismatch_error = Error(
    type="super_admin",
    message="User does not belong to the specified namespace",
)


# Error response models
class NamespaceNotFoundModel(ApiResponse):
    status: Status = Status.failed
    error: Error = namespace_not_found_error


class UserNotFoundModel(ApiResponse):
    status: Status = Status.failed
    error: Error = user_not_found_error


class UserNamespaceMismatchModel(ApiResponse):
    status: Status = Status.failed
    error: Error = user_namespace_mismatch_error


# Response dictionaries
namespace_not_found_response: dict[int, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": NamespaceNotFoundModel,
        "description": "Namespace not found",
    }
}

user_not_found_response: dict[int, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": UserNotFoundModel,
        "description": "User not found",
    }
}

user_namespace_mismatch_response: dict[int, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": UserNamespaceMismatchModel,
        "description": "User does not belong to namespace",
    }
}
