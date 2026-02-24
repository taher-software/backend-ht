from pydantic import BaseModel
from datetime import datetime
from .modelsIn import RestaurantHours, MenuSchedule, Surveys, CheckInOut


class SettingsResponse(BaseModel):
    id: int | None = None
    namespace_id: int
    restaurant_hours: RestaurantHours
    menu_schedule: MenuSchedule
    surveys: Surveys
    check_in_out: CheckInOut
    created_at: datetime | None = None
    updated_at: datetime | None = None
