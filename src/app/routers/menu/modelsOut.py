from pydantic import BaseModel
from typing import List, Optional
from src.app.globals.enum import MealEnum


class DishOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    img_url: Optional[str] = None


class CurrentMenuResponse(BaseModel):
    dishes: List[DishOut]
    meal: MealEnum
    meal_time_range: str


class TriggerNotificationResponse(BaseModel):
    """Response model for menu notification trigger endpoints"""

    total_namespaces: int
    queued_successfully: int
    failed_to_queue: int
    task_ids: List[str]
    failed_namespaces: List[int]
    message: str
