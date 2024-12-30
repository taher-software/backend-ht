from fastapi import APIRouter
from app.globals.generic_responses import validation_response
from app.globals.response import ApiResponse
from .modelsIn import StayRegistry
from fastapi import Depends
from app.globals.authentication import CurrentUserIdentifier
from app.resourcesController import guest_controller, stay_controller

router = APIRouter(prefix="/stays", tags=["Stays"], responses={**validation_response})


@router.post("/create")
def create_stay(
    payload: StayRegistry,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    guest_fields = ["guest_phone_number", "first_name", "last_name", "birth_date"]
    stay_fields = ["start_date", "end_date", "meal_plan", "stay_room"]
    guest = guest_controller.find_by_field("phone_number", payload.guest_phone_number)
    if not guest:
        guest_payload = dict()
        for field in guest_fields:
            field_value = getattr(payload, field)
            if field_value:
                guest_payload[field] = field_value
        guest_controller.create(guest_payload)

    stay_payload = dict(
        namespace_id=current_user["namespace_id"], guest_id=payload.guest_phone_number
    )
    for field in stay_fields:
        field_value = getattr(payload, field)
        if field_value:
            stay_payload[field] = field_value
    stay_controller.create(stay_payload)

    return ApiResponse(data="New stay saved successfully")
