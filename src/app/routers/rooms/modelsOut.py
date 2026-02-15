from pydantic import BaseModel


class RoomListItem(BaseModel):
    id: int
    room_number: str

    class Config:
        from_attributes = True
