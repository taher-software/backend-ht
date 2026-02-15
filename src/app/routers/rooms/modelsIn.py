from pydantic import BaseModel, Field


class CreateRoomsIn(BaseModel):
    start_room_number: int = Field(..., description="Starting room number")
    number_of_rooms: int = Field(1, ge=1, description="Number of rooms to create")


class UpdateRoomIn(BaseModel):
    new_room_number: int = Field(..., description="New room number")


class DeleteRoomsIn(BaseModel):
    room_ids: list[int] = Field(..., description="List of room IDs to delete")
