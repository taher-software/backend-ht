from src.app.resourcesController import (
    guest_controller,
    stay_controller,
    users_controller,
)
from src.app.db.models import Stay
from .modelsIn import StayRegistry, StayUpdate
from src.app.globals.response import ApiResponse
from fastapi import HTTPException, status
from src.app.globals.decorators import transactional
from sqlalchemy import and_
from sqlalchemy.orm import selectinload
from datetime import date
from src.settings import client
from functools import lru_cache
import logging
from src.app.gcp import cloud_task_manager
from src.app.globals.enum import JobType


@transactional
def add_new_stay(payload: StayRegistry, current_user: dict, db=None) -> ApiResponse:

    user = users_controller.find_by_field("phone_number", payload.guest_phone_number)

    if user:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "cannot manage this stay as the guest is already registered with a user account",
        )

    guest = guest_controller.find_by_field("phone_number", payload.guest_phone_number)
    if not guest:
        guest_controller.create(
            dict(phone_number=payload.guest_phone_number), db=db, commit=False
        )

    stay_payload = dict(
        namespace_id=current_user["namespace_id"],
        guest_id=payload.guest_phone_number,
        start_date=payload.start_date,
        end_date=payload.end_date,
        meal_plan=payload.meal_plan.value,
        room_id=payload.room_id,
    )
    stay_controller.create(stay_payload, db=db, commit=False)

    # Schedule room reception survey with 2-hour delay (7200 seconds)
    try:
        task_id = cloud_task_manager.create_task(
            delay=7200,  # 2 hours = 7200 seconds
            namespace_id=current_user["namespace_id"],
            job_type=JobType.ROOM_RECEPTION_SURVEY,
            guest_id=payload.guest_phone_number,
        )
        logging.info(
            f"Scheduled room reception survey for guest {payload.guest_phone_number} "
            f"(task_id={task_id}, namespace={current_user['namespace_id']})"
        )
    except Exception as e:
        # Log the error but don't fail the stay creation
        logging.error(
            f"Failed to schedule room reception survey for guest {payload.guest_phone_number}: {str(e)}",
            exc_info=True,
        )

    return ApiResponse(data="New stay saved successfully")


@transactional
def update_stay(stay_id: int, payload: StayUpdate, namespace_id: int, db=None):
    stay = stay_controller.find_by_id(stay_id)
    if not stay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stay with id {stay_id} not found",
        )

    if stay["namespace_id"] != namespace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Stay does not belong to your namespace",
        )

    update_data = payload.model_dump(exclude_unset=True)
    stay_update = {}

    if "guest_phone_number" in update_data:
        new_phone = update_data["guest_phone_number"]
        if new_phone != stay["guest_id"]:
            if not guest_controller.find_by_field("phone_number", new_phone):
                guest_controller.create(dict(phone_number=new_phone), db=db, commit=False)
            stay_update["guest_id"] = new_phone

    for field in ("start_date", "end_date", "meal_plan", "room_id"):
        if field in update_data:
            value = update_data[field]
            stay_update[field] = value.value if field == "meal_plan" else value

    if stay_update:
        stay_controller.update(stay_id, stay_update, commit=False, db=db)

    return stay_controller.find_by_id(stay_id)


def get_active_stays(namespace_id: int, db=None):
    today = date.today()
    stays = (
        db.query(Stay)
        .filter(
            and_(
                Stay.namespace_id == namespace_id,
                Stay.start_date <= today,
                Stay.end_date >= today,
            )
        )
        .order_by(Stay.start_date.desc())
        .all()
    )
    return [stay.to_dict() for stay in stays]


@transactional
def delete_stays(stay_ids: list[int], namespace_id: int, db=None):
    for stay_id in stay_ids:
        stay = stay_controller.find_by_id(stay_id)
        if not stay:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stay with id {stay_id} not found",
            )
        if stay["namespace_id"] != namespace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Stay with id {stay_id} does not belong to your namespace",
            )
        stay_controller.delete(stay_id, commit=False, db=db)

    return len(stay_ids)


def get_stay_with_guest(stay_id: int, namespace_id: int, db=None):
    stay = (
        db.query(Stay)
        .options(selectinload(Stay.guest))
        .filter(Stay.id == stay_id)
        .first()
    )
    if not stay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stay with id {stay_id} not found",
        )
    if stay.namespace_id != namespace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Stay does not belong to your namespace",
        )
    result = stay.to_dict()
    result["guest"] = stay.guest.to_dict() if stay.guest else None
    return result
