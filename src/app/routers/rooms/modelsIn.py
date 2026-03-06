from pydantic import BaseModel, Field


class CreateRoomsIn(BaseModel):
    start_room_number: str = Field(..., description="Starting room number (e.g. '101' or 'A120')")
    number_of_rooms: int = Field(1, ge=1, description="Number of rooms to create")
    floor: int = Field(..., description="Floor number")
    area: str = Field(..., description="Area name")


class UpdateRoomIn(BaseModel):
    floor: int | None = Field(None, description="Floor number")
    area: str | None = Field(None, description="Area name")


class DeleteRoomsIn(BaseModel):
    room_ids: list[int] = Field(..., description="List of room IDs to delete")
