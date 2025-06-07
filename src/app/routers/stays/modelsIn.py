from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from src.app.globals.enum import MealPlan


class StayRegistry(BaseModel):
    guest_phone_number: str = Field(...)
    first_name: str = Field(...)
    last_name: str = Field(...)
    birth_date: str | None = Field(None)
    start_date: str = Field(...)
    end_date: str = Field(...)
    meal_plan: MealPlan = Field(...)
    stay_room: str = Field(...)

    @field_validator("start_date", "end_date", mode="after")
    @classmethod
    def parse_stay_dates(cls, value: str) -> str:
        if value:
            return datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator("birth_date", mode="after")
    @classmethod
    def parse_birth_date(cls, value: str) -> str:
        if value:
            return datetime.strptime(value, "%Y/%m/%d")
        return value
