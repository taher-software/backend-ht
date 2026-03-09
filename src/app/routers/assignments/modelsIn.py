from pydantic import BaseModel, Field
from datetime import date
from typing import List


class AssignmentCreateIn(BaseModel):
    room_id: int = Field(...)
    housekeeper_id: int = Field(...)
    date: date = Field(...)


class AssignmentDeleteIn(BaseModel):
    assignment_ids: list[int] = Field(..., min_length=1)


class Assignment(BaseModel):
    room_id: int = Field(...)
    housekeeper_id: int = Field(...)


class CreatePlanIn(BaseModel):
    date: date = Field(...)
    assignments: List[Assignment] = Field(..., min_length=1)
