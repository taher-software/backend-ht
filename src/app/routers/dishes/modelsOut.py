from pydantic import BaseModel, HttpUrl, Field
from typing import Optional


class DishesOut(BaseModel):
    id: int | None = Field(None)
    name: str
    description: Optional[str] = None
    img_url: Optional[HttpUrl] = None
    # Add other fields as needed


class DishesListOut(BaseModel):
    total: int | None = None
    items: list[DishesOut]
