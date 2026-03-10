import re
from sqlalchemy import func
from src.app.resourcesController import room_controller
from src.app.globals.decorators import transactional
from src.app.db.models.room import Room
from sqlalchemy import cast, Integer, asc
from fastapi import HTTPException, status


def _resolve_area(namespace_id: int, area: str, db) -> str:
    existing = (
        db.query(Room.area)
        .filter(
            Room.namespace_id == namespace_id,
            func.lower(Room.area) == area.lower(),
        )
        .first()
    )
    if existing:
        return existing.area
    return area.title()


def _generate_room_numbers(start_room_number: str, number_of_rooms: int) -> list[str]:
    match = re.match(r"^([A-Za-z]*)(\d+)$", start_room_number)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid room number format: '{start_room_number}'. Expected format like '101' or 'A120'.",
        )
    prefix = match.group(1)
    start_num = int(match.group(2))
    return [f"{prefix}{start_num + i}" for i in range(number_of_rooms)]


@transactional
def create_rooms(
    namespace_id: int,
    start_room_number: str,
    number_of_rooms: int,
    floor: int,
    area: str,
    db=None,
):
    resolved_area = _resolve_area(namespace_id, area, db)
    room_numbers = _generate_room_numbers(start_room_number, number_of_rooms)

    created_rooms = []
    for room_number in room_numbers:
        existing = (
            db.query(Room)
            .filter(
                Room.namespace_id == namespace_id,
                func.lower(Room.area) == resolved_area.lower(),
                Room.room_number == room_number,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room '{room_number}' already exists in area '{resolved_area}'.",
            )

        room = room_controller.create(
            {
                "namespace_id": namespace_id,
                "room_number": room_number,
                "area": resolved_area,
                "floor": floor,
            },
            db=db,
            commit=False,
        )
        created_rooms.append(room)

    return created_rooms


def update_room(namespace_id: int, room_id: int, floor: int | None, area: str | None, db):
    room = (
        db.query(Room)
        .filter(Room.id == room_id, Room.namespace_id == namespace_id)
        .first()
    )
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found in your namespace.",
        )

    update_data = {}

    if area is not None:
        existing_area = (
            db.query(Room.area)
            .filter(
                Room.namespace_id == namespace_id,
                func.lower(Room.area) == area.lower(),
            )
            .first()
        )
        if not existing_area:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Area '{area}' does not exist in your namespace.",
            )
        update_data["area"] = existing_area.area

    if floor is not None:
        update_data["floor"] = floor

    if not update_data:
        return room.to_dict()

    return room_controller.update(room_id, update_data, db=db)


def get_all_rooms(namespace_id: int):
    db = room_controller.db
    rooms = (
        db.query(Room)
        .filter(Room.namespace_id == namespace_id)
        .order_by(Room.area.asc(), asc(cast(Room.room_number, Integer)))
        .all()
    )
    return [room.to_dict() for room in rooms]


def get_all_areas(namespace_id: int) -> list[str]:
    db = room_controller.db
    rows = (
        db.query(Room.area)
        .filter(Room.namespace_id == namespace_id, Room.area.isnot(None))
        .distinct()
        .order_by(Room.area.asc())
        .all()
    )
    return [row.area for row in rows]


@transactional
def delete_rooms(namespace_id: int, room_ids: list[int], db=None):
    for room_id in room_ids:
        room = (
            db.query(Room)
            .filter(Room.id == room_id, Room.namespace_id == namespace_id)
            .first()
        )
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with id {room_id} not found in your namespace.",
            )
        room_controller.delete(room_id, commit=False, db=db)

    return len(room_ids)
