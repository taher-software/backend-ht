from pydantic import BaseModel
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


class SettingsCreate(SettingsBase):
    pass


class SettingsUpdate(BaseModel):
    restaurant_hours: Optional[RestaurantHours] = None
    menu_schedule: Optional[MenuSchedule] = None
    surveys: Optional[Surveys] = None
    check_in_out: Optional[CheckInOut] = None
