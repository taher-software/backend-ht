from pydantic import BaseModel
from datetime import time
from typing import Optional


class SettingsBase(BaseModel):
    # Meal times
    breakfast_start_time: time
    breakfast_end_time: time
    lunch_start_time: time
    lunch_end_time: time
    dinner_start_time: time
    dinner_end_time: time

    # Notification settings
    restaurant_survey_time: Optional[time] = None
    room_survey_time: Optional[time] = None
    breakfast_menu_time: Optional[time] = None
    lunch_menu_time: Optional[time] = None
    dinner_menu_time: Optional[time] = None

    # Check in/out times
    check_in_time: time
    check_out_time: time


class SettingsCreate(SettingsBase):
    pass


class SettingsUpdate(SettingsBase):
    # Meal times
    breakfast_start_time: time | None = None
    breakfast_end_time: time | None = None
    lunch_start_time: time | None = None
    lunch_end_time: time | None = None
    dinner_start_time: time | None = None
    dinner_end_time: time | None = None

    # Check in/out times
    check_in_time: time | None = None
    check_out_time: time | None = None
