from pydantic import BaseModel
from datetime import date, datetime


class AssignmentOut(BaseModel):
    id: int
    room_id: int
    housekeeper_id: int
    date: date
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
