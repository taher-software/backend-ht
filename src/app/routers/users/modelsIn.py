from src.app.db.models.users import Users
from pydantic import BaseModel, Field
from typing import Optional, List
from src.app.globals.schema_models import Role
from src.app.globals.response import ApiResponse
from pydantic import EmailStr
from datetime import datetime


class UserBase(BaseModel):
    phone_number: str = Field(..., pattern="^\+[1-9]\d{6,14}$")
    user_email: EmailStr
    first_name: str
    last_name: str
    role: Role
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


# First create a model for partial updates
class UserUpdate(BaseModel):
    phone_number: Optional[str] = Field(None, pattern="^\+[1-9]\d{6,14}$")
    user_email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    current_device_token: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    role: Optional[Role] = None


class UserOrm(BaseModel):
    id: int
    namespace_id: int
    phone_number: str
    user_email: EmailStr
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    role: Role
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
