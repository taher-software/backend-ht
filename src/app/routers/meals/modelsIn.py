from datetime import date
from pydantic import BaseModel, Field
from typing import List, Optional
from src.app.globals.enum import MealEnum


class MealCreateIn(BaseModel):
    meal_type: MealEnum = Field(...)
    meal_date: date = Field(...)
    dishes_ids: List[int] = Field(..., min_items=1)


class MealUpdateIn(BaseModel):
    meal_type: Optional[MealEnum] = None
    meal_date: Optional[date] = None
    dishes_ids: Optional[List[int]] = Field(None, min_items=1)


class DeleteMealsBatchIn(BaseModel):
    meal_ids: List[int] = Field(..., min_items=1)
