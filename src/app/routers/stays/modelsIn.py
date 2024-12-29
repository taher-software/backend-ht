from pydantic import BaseModel, Field
from datetime import datetime
from app.globals.enum import MealPlan


class StayRegistry(BaseModel):
    guest_phone_number: str = Field(...)
    first_name: str = Field(...)
    last_name: str = Field(...)
    birth_date: str | None = Field(None)
    start_date: datetime = Field(...)
    end_date: datetime = Field(...)
    meal_plan: MealPlan = Field(...)
    stay_room: str = Field(...)
