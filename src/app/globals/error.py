from pydantic import BaseModel
from typing import Optional


class Error(BaseModel):
    type: str
    message: str
    detail: str | None = None


class dbError(Error):
    type: str = "db"
    message: str = "db_error"


validation_error = Error(type="validation", message="validation_error", detail="")
not_authenticated = Error(type="auth", message="not_authenticated")
invalid_token = Error(type="auth", message="invalid_token")
expired_token = Error(type="auth", message="expired_token")
db_error = dbError(detail="")
