from datetime import date

from fastapi import HTTPException, status

from src.app.globals.decorators import transactional
from src.app.db.models.room import Room
from src.app.db.models.housekeepers import Housekeeper
from src.app.db.models.housekeeper_assignment import HousekeeperAssignment
from src.app.resourcesController import housekeeper_assignment_controller
from src.app.routers.assignments.modelsIn import Assignment


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
