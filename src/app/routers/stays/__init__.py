from fastapi import APIRouter
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from .modelsIn import StayRegistry
from fastapi import Depends
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.resourcesController import guest_controller, stay_controller
from .services import add_new_stay

router = APIRouter(prefix="/stays", tags=["Stays"], responses={**validation_response})


@router.post("/create")
def create_stay(
    payload: StayRegistry,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:

    return add_new_stay(payload, current_user)
