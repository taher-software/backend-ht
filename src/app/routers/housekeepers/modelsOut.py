from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class HousekeeperOut(BaseModel):
    id: int
    namespace_id: int
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
