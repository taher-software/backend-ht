from typing import Optional

from pydantic import BaseModel, Field


class HousekeeperCreateIn(BaseModel):
    first_name: str = Field(...)
    last_name: str = Field(...)


class HousekeeperUpdateIn(BaseModel):
    first_name: Optional[str] = Field(None)
    last_name: Optional[str] = Field(None)


class DeleteHousekeepersBatchIn(BaseModel):
    housekeeper_ids: list[int] = Field(..., min_length=1)
