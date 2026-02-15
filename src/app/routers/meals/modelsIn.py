from datetime import date
from pydantic import BaseModel, Field
from typing import List, Optional
from src.app.globals.enum import MealEnum


class MealCreateIn(BaseModel):
    meal_type: MealEnum = Field(...)
    meal_date: date = Field(...)
    dishes_ids: List[int] = Field(..., min_items=1)
