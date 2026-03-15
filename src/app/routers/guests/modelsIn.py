from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime
import json


class GuestFullProfileIn(BaseModel):
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    pref_language: str
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None

    @field_validator("birth_date", mode="after")
    @classmethod
    def parse_birth_date(cls, v):
        if v is not None:
            return datetime.strptime(v, "%Y-%m-%d").date()
        return v
    
    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values
