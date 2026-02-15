from pydantic import BaseModel
from typing import Optional, List


class MealOut(BaseModel):
    id: int
    meal_type: str
    namespace_id: int
    meal_date: str
    # Add other fields as needed


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
