from pydantic import Field, BaseModel, HttpUrl, EmailStr
from typing import Literal
from enum import Enum
from datetime import datetime


class Role(str, Enum):
    owner: str = "owner"
    admin: str = "admin"
    supervisor: str = "supervisor"
    dining_supervisor: str = "dining supervisor"
    housekeeping_supervisor: str = "housekeeping supervisor"
    maintenance_supervisor: str = "maintenance supervisor"
    guest_relations_supervisor: str = "guest relations supervisor"


role_categ_assoc = {
    "Housekeeping": "housekeeping supervisor",
    "Maintenance": "maintenance supervisor",
    "Guest Relations": "guest relations supervisor",
    "Dining": "dining supervisor",
    "unknown": "supervisor",
}


class NamespaceModel(BaseModel):
    hotel_name: str = Field(...)
    hotel_email: EmailStr | None = Field(None)
    hotel_phone_number: str | None = Field(None)
    hotel_website_url: HttpUrl | None = Field(None)
    hotel_star_rating: int | None = Field(None)
    business_registration_number: str = Field(...)
    tax_identification_number: str = Field(...)
    country: str = Field(...)
    province: str | None = Field(None)
    postal_code: str | None = Field(None)
    city: str | None = Field(None)
    number_of_rooms: int | None = Field(None)


class UsersModel(BaseModel):
    avatar_url: str = Field(None)
    user_email: EmailStr = Field(...)
    first_name: str = Field(...)
    last_name: str = Field(...)
    hashed_password: str = Field(None)
    role: Role = Field(default=Role.owner)
    phone_number: str = Field(..., pattern="^\+?[1-9]\d{1,14}$")


class GuestModel(BaseModel):
    phone_number: str = Field(..., pattern="^\+?[1-9]\d{1,14}$")
    first_name: str = Field(...)
    last_name: str = Field(...)
    birth_date: datetime | None = Field(None)
    photo_url: str = Field(...)
