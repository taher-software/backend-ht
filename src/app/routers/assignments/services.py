from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, cast, Integer, asc

from src.app.globals.decorators import transactional
from src.app.db.models.namespace import Namespace
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


def get_namespaces_require_reminder_for_housekeeper_schedule(db) -> list[int]:
    """
    Return IDs of namespaces that satisfy both conditions:

    1. The current UTC time, converted to the namespace's local timezone,
       is less than 6 hours after midday (12:00).  In other words, the
       local time is between 12:00 and 18:00 — we only nag supervisors
       during the afternoon window.

    2. There are no HousekeeperAssignment records dated tomorrow for
       that namespace, meaning the schedule has not been planned yet.

    Args:
        db: SQLAlchemy database session.

    Returns:
        List of namespace IDs that need a reminder.
    """
    tomorrow = date.today() + timedelta(days=1)
    now_utc = datetime.now(ZoneInfo("UTC"))

    # Pre-fetch tomorrow's scheduled namespace IDs in one query
    scheduled_ns_ids = {
        row.namespace_id
        for row in db.query(HousekeeperAssignment.namespace_id)
        .filter(HousekeeperAssignment.date == tomorrow)
        .distinct()
        .all()
    }

    results = []
    for ns in db.query(Namespace).all():
        # Skip namespaces that already have a plan for tomorrow
        if ns.id in scheduled_ns_ids:
            continue

        # Convert current UTC time to the namespace's local timezone
        try:
            tz = ZoneInfo(ns.timezone)
        except Exception:
            continue

        now_local = now_utc.astimezone(tz)
        midday = now_local.replace(hour=12, minute=0, second=0, microsecond=0)

        # Condition: local time is within 6 hours after midday
        hours_since_midday = (now_local - midday).total_seconds() / 3600
        if 0 <= hours_since_midday < 6:
            results.append(ns.id)

    return results
