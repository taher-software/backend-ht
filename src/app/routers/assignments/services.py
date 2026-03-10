from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, cast, Integer, asc

from src.app.globals.decorators import transactional
from src.app.db.models.room import Room
from src.app.db.models.housekeepers import Housekeeper
from src.app.db.models.housekeeper_assignment import HousekeeperAssignment
from src.app.resourcesController import housekeeper_assignment_controller
from src.app.routers.assignments.modelsIn import Assignment


def get_next_day_by_area(namespace_id: int, area: str, db) -> dict:
    area_exists = (
        db.query(Room.area)
        .filter(
            Room.namespace_id == namespace_id,
            func.lower(Room.area) == area.lower(),
        )
        .first()
    )
    if not area_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area '{area}' not found in your namespace.",
        )

    rooms = (
        db.query(Room)
        .filter(
            Room.namespace_id == namespace_id,
            func.lower(Room.area) == area.lower(),
        )
        .order_by(Room.floor.asc(), asc(cast(Room.room_number, Integer)))
        .all()
    )

    tomorrow = date.today() + timedelta(days=1)
    room_ids = [room.id for room in rooms]

    assignments = (
        db.query(HousekeeperAssignment)
        .filter(
            HousekeeperAssignment.namespace_id == namespace_id,
            HousekeeperAssignment.room_id.in_(room_ids),
            HousekeeperAssignment.date == tomorrow,
        )
        .all()
    )

    floors: dict[str, list] = {}
    for room in rooms:
        floor_label = f"Floor {room.floor}" if room.floor is not None else "Unassigned"
        floors.setdefault(floor_label, [])
        floors[floor_label].append({"id": room.id, "number": room.room_number})

    area_list = [{"floor": floor, "rooms": r} for floor, r in floors.items()]
    assignment_list = [
        {"room_id": a.room_id, "housekeeper_id": a.housekeeper_id}
        for a in assignments
    ]

    return {"area": area_list, "assignment": assignment_list}


def get_today_plan_by_area(namespace_id: int, area: str, db) -> list[dict]:
    area_exists = (
        db.query(Room.area)
        .filter(
            Room.namespace_id == namespace_id,
            func.lower(Room.area) == area.lower(),
        )
        .first()
    )
    if not area_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area '{area}' not found in your namespace.",
        )

    room_ids = [
        row.id
        for row in db.query(Room.id)
        .filter(
            Room.namespace_id == namespace_id,
            func.lower(Room.area) == area.lower(),
        )
        .all()
    ]

    today = date.today()

    assignments = (
        db.query(HousekeeperAssignment)
        .filter(
            HousekeeperAssignment.namespace_id == namespace_id,
            HousekeeperAssignment.room_id.in_(room_ids),
            HousekeeperAssignment.date == today,
        )
        .all()
    )

    return [
        {"room_id": a.room_id, "housekeeper_id": a.housekeeper_id}
        for a in assignments
    ]


@transactional
def create_plan(
    namespace_id: int,
    plan_date: date,
    assignments: list[Assignment],
    db=None,
):
    for item in assignments:
        room = (
            db.query(Room)
            .filter(
                Room.id == item.room_id,
                Room.namespace_id == namespace_id,
            )
            .first()
        )
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with id {item.room_id} not found.",
            )

        housekeeper = (
            db.query(Housekeeper)
            .filter(
                Housekeeper.id == item.housekeeper_id,
                Housekeeper.namespace_id == namespace_id,
            )
            .first()
        )
        if not housekeeper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Housekeeper with id {item.housekeeper_id} not found."
                ),
            )

        existing = (
            db.query(HousekeeperAssignment)
            .filter(
                HousekeeperAssignment.namespace_id == namespace_id,
                HousekeeperAssignment.room_id == item.room_id,
                HousekeeperAssignment.date == plan_date,
            )
            .first()
        )

        if existing:
            housekeeper_assignment_controller.update(
                existing.id,
                {"housekeeper_id": item.housekeeper_id},
                db=db,
                commit=False,
            )
        else:
            housekeeper_assignment_controller.create(
                {
                    "namespace_id": namespace_id,
                    "room_id": item.room_id,
                    "housekeeper_id": item.housekeeper_id,
                    "date": plan_date,
                },
                db=db,
                commit=False,
            )
