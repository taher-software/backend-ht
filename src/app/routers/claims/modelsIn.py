from pydantic import BaseModel, Field, model_validator
import json


class ClaimIn(BaseModel):
    text: str = Field(None, min_length=10, max_length=1000)
    voice_duration: float | None = Field(None)

    @model_validator(mode="before")
    def check_data(cls, values):
        if isinstance(values, str):
            values = json.loads(values)
        return values
