from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class MenuOut(BaseModel):
    id: int
    dishes_id: int
    meal_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MealWithMenus(BaseModel):
    id: int
    meal_type: str
    namespace_id: int
    meal_date: date
    created_at: datetime
    updated_at: datetime
    menus: list[MenuOut] = []

    class Config:
        from_attributes = True


class MealOut(BaseModel):
    id: int
    meal_type: str
    namespace_id: int
    meal_date: str


class QueuedTask(BaseModel):
    """Information about a queued task for a namespace"""

    namespace_id: int
    task_id: str
    status: str  # "queued"


class FailedNamespace(BaseModel):
    """Information about a namespace that failed to queue"""

    namespace_id: int
    error: str


class MenuReminderBatchResponse(BaseModel):
    """Response for batch meal reminder endpoints"""

    message: str
    total_namespaces: int
    queued_tasks: List[QueuedTask]
    failed_namespaces: List[FailedNamespace] = []
