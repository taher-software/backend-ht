from typing import Optional

from pydantic import BaseModel, Field, model_validator
import json


class HousekeeperCreateIn(BaseModel):
    first_name: str = Field(...)
    last_name: str = Field(...)
    
    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values


class HousekeeperUpdateIn(BaseModel):
    first_name: Optional[str] = Field(None)
    last_name: Optional[str] = Field(None)
    
    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values


class DeleteHousekeepersBatchIn(BaseModel):
    housekeeper_ids: list[int] = Field(..., min_length=1)
