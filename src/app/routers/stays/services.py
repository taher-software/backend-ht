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

    guest_fields = {
        "guest_phone_number": "phone_number",
        "first_name": "first_name",
        "last_name": "last_name",
        "birth_date": "birth_date",
        "pref_language": "pref_language",
        "nationality": "nationality",
        "country_of_residence": "country_of_residence",
    }
    stay_fields = ["start_date", "end_date", "meal_plan", "room_id"]
    guest = guest_controller.find_by_field("phone_number", payload.guest_phone_number)
    if not guest:
        guest_payload = dict()
        for field in guest_fields.keys():
            if field != "pref_language":
                field_value = getattr(payload, field)
                if field_value:
                    guest_payload[guest_fields[field]] = field_value
            else:
                nationality = payload.nationality
                country_of_residence = payload.country_of_residence
                guest_payload["pref_language"] = infer_guest_mother_language(
                    nationality, country_of_residence
                )
        guest_controller.create(guest_payload, db=db, commit=False)

    stay_payload = dict(
        namespace_id=current_user["namespace_id"], guest_id=payload.guest_phone_number
    )
    for field in stay_fields:
        field_value = getattr(payload, field)
        if field_value:
            if field == "meal_plan":
                field_value = field_value.value
            stay_payload[field] = field_value
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


@lru_cache
def infer_guest_mother_language(nationality: str, country_of_residence: str) -> str:
    prompt = (
        f"The guest's nationality is {nationality} and their country of residence is {country_of_residence}. "
        "What is their most likely mother language?. give me only the mother language as response"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI language detection system. "
                        "Given a guest's nationality and country of residence, infer their mother language."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"failed to define guest mother language: {str(e)}")
        return None


GUEST_FIELDS_MAP = {
    "first_name": "first_name",
    "last_name": "last_name",
    "birth_date": "birth_date",
    "nationality": "nationality",
    "country_of_residence": "country_of_residence",
}

STAY_FIELDS = ["start_date", "end_date", "meal_plan", "room_id", "guest_phone_number"]


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

    update_data = payload.dict(exclude_unset=True)
    guest_id = stay["guest_id"]

    # Update guest fields if provided
    guest_update = {}
    for field, guest_field in GUEST_FIELDS_MAP.items():
        if field in update_data:
            guest_update[guest_field] = update_data[field]

    if guest_update:
        # Only allow guest update if guest is associated to this stay only
        all_guest_stays = stay_controller.find_by_field("guest_id", guest_id, all=True)
        if len(all_guest_stays) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update guest information: guest is associated with multiple stays",
            )
        guest_controller.update(
            guest_id, guest_update, resource_key="phone_number", commit=False, db=db
        )

    # Update stay fields if provided
    stay_update = {}
    for field in STAY_FIELDS:
        if field in update_data:
            value = update_data[field]
            if field == "meal_plan":
                value = value.value
            if field == "guest_phone_number":
                stay_update["guest_id"] = value
            else:
                stay_update[field] = value

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
        .order_by(Stay.start_date)
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
