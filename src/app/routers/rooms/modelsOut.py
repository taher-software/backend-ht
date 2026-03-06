from pydantic import BaseModel


class RoomListItem(BaseModel):
    id: int
    room_number: str
    area: str | None = None
    floor: int | None = None

    class Config:
        from_attributes = True
