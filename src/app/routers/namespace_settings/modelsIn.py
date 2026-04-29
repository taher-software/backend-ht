from pydantic import BaseModel, field_validator
from datetime import time
from typing import Optional


class Breakfast(BaseModel):
    start: time
    end: time


class Lunch(BaseModel):
    start: time
    end: time


class Dinner(BaseModel):
    start: time
    end: time


class RestaurantHours(BaseModel):
    breakfast: Breakfast
    lunch: Lunch
    dinner: Dinner


class MenuSchedule(BaseModel):
    breakfast_time: time
    lunch_time: time
    dinner_time: time


class Surveys(BaseModel):
    restaurant_time: time
    room_time: time


class CheckInOut(BaseModel):
    checkin_time: time
    checkout_time: time


class SettingsBase(BaseModel):
    restaurant_hours: RestaurantHours
    menu_schedule: MenuSchedule
    surveys: Optional[Surveys] = None
    check_in_out: CheckInOut
    satisfaction_threshold: Optional[float] = None
    claim_resolution_time: Optional[int] = None

    @field_validator("satisfaction_threshold")
    @classmethod
    def _validate_satisfaction_threshold(cls, v):
        if v is None:
            return v
        if not (0 < v <= 100):
            raise ValueError("satisfaction_threshold must be in (0, 100]")
        return v


class SettingsCreate(SettingsBase):
    pass


class SettingsUpdate(BaseModel):
    restaurant_hours: Optional[RestaurantHours] = None
    menu_schedule: Optional[MenuSchedule] = None
    surveys: Optional[Surveys] = None
    check_in_out: Optional[CheckInOut] = None
    satisfaction_threshold: Optional[float] = None
    claim_resolution_time: Optional[int] = None

    @field_validator("satisfaction_threshold")
    @classmethod
    def _validate_satisfaction_threshold(cls, v):
        if v is None:
            return v
        if not (0 < v <= 100):
            raise ValueError("satisfaction_threshold must be in (0, 100]")
        return v
