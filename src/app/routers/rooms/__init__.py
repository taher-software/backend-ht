from fastapi import APIRouter, Depends, HTTPException
from src.app.db.orm import get_db
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.generic_responses import validation_response
from src.app.globals.schema_models import Role
from .modelsIn import CreateRoomsIn, UpdateRoomIn, DeleteRoomsIn
from .modelsOut import RoomListItem
from .services import create_rooms, update_room, get_all_rooms, delete_rooms, get_all_areas

router = APIRouter(prefix="/rooms", tags=["Rooms"], responses={**validation_response})

ALLOWED_ROLES = {
    Role.owner.value,
    Role.admin.value,
    Role.supervisor.value,
    Role.housekeeping_supervisor.value,
}


def _check_role(current_user: dict):
    if not set(current_user.get("role", [])) & ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage rooms.",
        )


@router.post("/")
def create(
    payload: CreateRoomsIn,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """
    Create new rooms starting from start_room_number.

    Creates number_of_rooms rooms with sequential room numbers
    from start_room_number to start_room_number + number_of_rooms - 1.
    """
    _check_role(current_user)
    rooms = create_rooms(
        namespace_id=current_user["namespace_id"],
        start_room_number=payload.start_room_number,
        number_of_rooms=payload.number_of_rooms,
        floor=payload.floor,
        area=payload.area,
    )

    return ApiResponse(data=[RoomListItem(**room) for room in rooms])


@router.patch("/{room_id}")
def update(
    room_id: int,
    payload: UpdateRoomIn,
    db=Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """Update floor and/or area of a specific room."""
    _check_role(current_user)
    updated_room = update_room(
        namespace_id=current_user["namespace_id"],
        room_id=room_id,
        floor=payload.floor,
        area=payload.area,
        db=db,
    )

    return ApiResponse(data=RoomListItem(**updated_room))


@router.get("/")
def list_all(
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """List all rooms for the current user's namespace."""
    _check_role(current_user)
    rooms = get_all_rooms(namespace_id=current_user["namespace_id"])

    return ApiResponse(
        data=[RoomListItem(**room) for room in rooms] 
    )


@router.get("/areas")
def list_areas(
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """List all distinct areas for the current user's namespace."""
    _check_role(current_user)
    areas = get_all_areas(namespace_id=current_user["namespace_id"])
    return ApiResponse(data=areas)


@router.delete("/")
def delete(
    payload: DeleteRoomsIn,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """Delete a list of rooms by their IDs."""
    _check_role(current_user)
    deleted_count = delete_rooms(namespace_id=current_user["namespace_id"], room_ids=payload.room_ids)

    return ApiResponse(data={"deleted_count": deleted_count})
