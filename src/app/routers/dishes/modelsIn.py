from pydantic import BaseModel, HttpUrl, model_validator
from typing import Optional
import json


class DishesIn(BaseModel):
    name: str
    description: Optional[str] = None
    img_url: Optional[HttpUrl] = None  # Accepts a URL if provided

    # Add other fields as needed
    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values


class DishesUpdate(DishesIn):
    name: Optional[str] = None
