from src.app.resourcesController import room_controller
from src.app.globals.decorators import transactional
from src.app.db.models.room import Room
from sqlalchemy import cast, Integer, desc
from fastapi import HTTPException, status


@transactional
def create_rooms(namespace_id: int, start_room_number: int, number_of_rooms: int, db=None):
    created_rooms = []
    for i in range(number_of_rooms):
        room_number = str(start_room_number + i)
        room = room_controller.create(
            {"namespace_id": namespace_id, "room_number": room_number},
            db=db,
            commit=False,
        )
        created_rooms.append(room)

    return created_rooms


def update_room_number(room_id: int, new_room_number: int, db=None):
    room = room_controller.find_by_id(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found",
        )

    updated_room = room_controller.update(
        room_id, {"room_number": str(new_room_number)}, db=db
    )
    return updated_room


def get_all_rooms(namespace_id: int):
    db = room_controller.db
    rooms = (
        db.query(Room)
        .filter(Room.namespace_id == namespace_id)
        .order_by(desc(cast(Room.room_number, Integer)))
        .all()
    )
    return [room.to_dict() for room in rooms]


@transactional
def delete_rooms(room_ids: list[int], db=None):
    for room_id in room_ids:
        room = room_controller.find_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with id {room_id} not found",
            )
        room_controller.delete(room_id, commit=False, db=db)

    return len(room_ids)
