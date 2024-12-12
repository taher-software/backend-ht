from typing import Any
from fastapi import status
from pydantic import BaseModel
from .response import ApiResponse
from .status import Status
from .error import (
    validation_error,
    Error,
    not_authenticated,
    invalid_token,
    expired_token,
    db_error,
)


class ValidationModel(ApiResponse):
    status: Status = Status.failed
    error: Error = validation_error


class NotAuthenticatedModel(ApiResponse):
    status: Status = Status.failed
    error: Error = not_authenticated


class InvalidTokenModel(ApiResponse):
    status: Status = Status.failed
    error: Error = invalid_token


class ExpiredTokenModel(ApiResponse):
    status: Status = Status.failed
    error: Error = expired_token


class dbErrorModel(ApiResponse):
    status: Status = Status.failed
    error: Error = db_error


validation_response: dict[int, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ValidationModel,
        "description": "Validation Error",
    }
}

not_authenticated_response: dict[int, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": NotAuthenticatedModel,
        "description": "Not Authenticated Error",
    }
}

invalid_token_response: dict[int, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {
        "model": InvalidTokenModel,
        "description": "Invalid Token",
    }
}

expired_token_response: dict[int, dict[str, Any]] = {
    status.HTTP_410_GONE: {
        "model": InvalidTokenModel,
        "description": "Expired Token",
    }
}

db_error_response: dict[int, dict[str, Any]] = {
    status.HTTP_406_NOT_ACCEPTABLE: {
        "model": dbErrorModel,
        "description": "Db Error",
    }
}
