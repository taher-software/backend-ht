from pydantic import BaseModel
from datetime import time, datetime
from typing import Optional


class SettingsResponse(BaseModel):
    id: int | None = None
    namespace_id: int

    # Meal times
    breakfast_start_time: time
    breakfast_end_time: time
    lunch_start_time: time
    lunch_end_time: time
    dinner_start_time: time
    dinner_end_time: time

    # Notification settings
    restaurant_survey_time: time
    room_survey_time: time
    breakfast_menu_time: time
    lunch_menu_time: time
    dinner_menu_time: time

    # Check in/out times
    check_in_time: time
    check_out_time: time

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
