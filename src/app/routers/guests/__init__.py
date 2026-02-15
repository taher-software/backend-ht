from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.resourcesController import guest_controller

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
