from src.app.db.models.users import Users
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from src.app.globals.schema_models import Role
from src.app.globals.response import ApiResponse
from pydantic import EmailStr
from datetime import datetime
import json


class UserBase(BaseModel):
    phone_number: str = Field(..., pattern="^\+[1-9]\d{6,14}$")
    user_email: EmailStr | None = None
    first_name: str
    last_name: str
    role: list[Role]
    avatar_url: Optional[str] = None

    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


# First create a model for partial updates
class UserUpdate(BaseModel):
    phone_number: Optional[str] = Field(None, pattern="^\+[1-9]\d{6,14}$")
    user_email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    current_device_token: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    role: list[Role] | None = None  # Allow role updates as well

    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values


class UserOrm(BaseModel):
    id: int
    namespace_id: int
    phone_number: str
    user_email: EmailStr
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    role: list[Role]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AddRoleRequest(BaseModel):
    role: Role = Field(..., description="New role to add to user")


class RemoveRoleRequest(BaseModel):
    role: Role = Field(..., description="Role to remove from user")
