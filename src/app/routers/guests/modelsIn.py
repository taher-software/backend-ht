from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime
import json


class GuestFullProfileIn(BaseModel):
    first_name: str
    last_name: str
    pref_language: str
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    
    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values
