from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class GuestFullProfileIn(BaseModel):
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    current_device_token: str
    pref_language: str
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None

    @field_validator("birth_date", mode="after")
    @classmethod
    def parse_birth_date(cls, v):
        if v is not None:
            return datetime.strptime(v, "%Y-%m-%d").date()
        return v
