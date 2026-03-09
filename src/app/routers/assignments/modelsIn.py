from pydantic import BaseModel, Field
from datetime import date
from typing import List

class Assignment(BaseModel):
    room_id: int = Field(...)
    housekeeper_id: int = Field(...)


class CreatePlanIn(BaseModel):
    plan_date: date = Field(...)
    assignments: List[Assignment] = Field(..., min_length=1)
