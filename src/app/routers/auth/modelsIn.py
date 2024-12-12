from pydantic import BaseModel, Field, HttpUrl, EmailStr, model_validator
from typing import Any
import json


class NamespaceRegistry(BaseModel):
    hotel_name: str = Field(...)
    hotel_email: str | None = Field(None)
    hotel_phone_number: str | None = Field(None)
    hotel_website_url: HttpUrl | None = Field(None)
    hotel_star_rating: int | None = Field(None)
    business_registration_number: str = Field(...)
    tax_identification_number: str = Field(...)
    country: str = Field(...)
    province: str = Field(None)
    postal_code: str = Field(...)
    city: str | None = None
    number_of_rooms: int | None = None
    first_name: str = Field(...)
    last_name: str = Field(...)
    password: str = Field(...)
    user_email: EmailStr = Field(...)
    phone_number: str = Field(..., pattern="^\+?[1-9]\d{1,14}$")

    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values
