from src.app.resourcesController import (
    guest_controller,
    stay_controller,
    users_controller,
)
from .modelsIn import StayRegistry
from src.app.globals.response import ApiResponse
from fastapi import HTTPException, status
from src.app.globals.decorators import transactional


@transactional
def add_new_stay(payload: StayRegistry, current_user: dict, db=None) -> ApiResponse:

    user = users_controller.find_by_field("phone_number", current_user["phone_number"])

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
    }
    stay_fields = ["start_date", "end_date", "meal_plan", "stay_room"]
    guest = guest_controller.find_by_field("phone_number", payload.guest_phone_number)
    if not guest:
        guest_payload = dict()
        for field in guest_fields:
            field_value = getattr(payload, field)
            if field_value:
                guest_payload[guest_fields[field]] = field_value
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

    return ApiResponse(data="New stay saved successfully")
