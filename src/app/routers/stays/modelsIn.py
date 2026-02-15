from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from src.app.globals.enum import MealPlan


class StayRegistry(BaseModel):
    guest_phone_number: str = Field(..., pattern="^\+?[1-9]\d{1,14}$")
    first_name: str = Field(...)
    last_name: str = Field(...)
    birth_date: str | None = Field(None)
    start_date: str = Field(...)
    end_date: str = Field(...)
    meal_plan: MealPlan = Field(...)
    room_id: int = Field(...)
    nationality: str = Field(...)
    country_of_residence: str = Field(...)

    @field_validator("start_date", "end_date", mode="after")
    @classmethod
    def parse_stay_dates(cls, value: str) -> str:
        if value:
            return datetime.strptime(value, "%Y-%m-%d").date()
        return value

    @field_validator("birth_date", mode="after")
    @classmethod
    def parse_birth_date(cls, value: str) -> str:
        if value:
            return datetime.strptime(value, "%Y/%m/%d").date()
        return value


class StayUpdate(BaseModel):
    guest_phone_number: str | None = Field(None, pattern="^\+?[1-9]\d{1,14}$")
    first_name: str | None = None
    last_name: str | None = None
    birth_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    meal_plan: MealPlan | None = None
    room_id: int | None = None
    nationality: str | None = None
    country_of_residence: str | None = None

    @field_validator("start_date", "end_date", mode="after")
    @classmethod
    def parse_stay_dates(cls, value: str) -> str:
        if value:
            return datetime.strptime(value, "%Y-%m-%d").date()
        return value

    @field_validator("birth_date", mode="after")
    @classmethod
    def parse_birth_date(cls, value: str) -> str:
        if value:
            return datetime.strptime(value, "%Y/%m/%d").date()
        return value


class DeleteStaysIn(BaseModel):
    stay_ids: list[int] = Field(..., description="List of stay IDs to delete")


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
