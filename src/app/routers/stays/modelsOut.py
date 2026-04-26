from datetime import datetime, date
from pydantic import BaseModel, Field
from src.app.globals.enum import MealPlan
from src.app.routers.rooms.modelsOut import RoomListItem


class StayOrm(BaseModel):
    id: int = Field(...)
    namespace_id: int = Field(...)
    start_date: date = Field(...)
    end_date: date = Field(...)
    guest_id: str = Field(...)
    meal_plan: MealPlan = Field(...)
    room_id: int = Field(...)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)

    class Config:
        from_attributes = True


class StayOut(StayOrm):
    room: RoomListItem = Field(...)
