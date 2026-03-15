from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Body
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.resourcesController import guest_controller
from src.app.db.orm import get_db
from .modelsIn import GuestFullProfileIn
from .services import update_guest_full_profile, update_guest_avatar

router = APIRouter(prefix="/guests", tags=["Guests"], responses={**validation_response})


@router.get("/")
def get_guest(
    phone_number: str = Query(...),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """Get a guest by phone number."""
    guest = guest_controller.find_by_field("phone_number", phone_number)
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found.",
        )
    return ApiResponse(data=guest)


@router.patch("/full_profile", response_model=ApiResponse)
def full_profile(
    payload: GuestFullProfileIn = Body(...),
    phone_number: str = Query(...),
    avatar: UploadFile = File(None),
    db=Depends(get_db),
) -> ApiResponse:
    update_guest_full_profile(payload, {"phone_number": phone_number}, avatar, db)
    return ApiResponse(data="Profile updated successfully")


@router.patch("/update_avatar", response_model=ApiResponse)
def update_avatar(
    avatar: UploadFile = File(...),
    current_user: dict = Depends(CurrentUserIdentifier(who="guest")),
    db=Depends(get_db),
) -> ApiResponse:
    update_guest_avatar(current_user, avatar, db)
    return ApiResponse(data="Avatar updated successfully")
