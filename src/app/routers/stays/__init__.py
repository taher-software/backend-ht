from fastapi import APIRouter, Depends, HTTPException
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.schema_models import Role
from src.app.db.orm import get_db
from .modelsIn import StayRegistry, StayUpdate, DeleteStaysIn
from .modelsOut import StayOrm, StayOut
from .services import add_new_stay, update_stay, get_active_stays, delete_stays, get_stay_with_guest

router = APIRouter(prefix="/stays", tags=["Stays"], responses={**validation_response})


def _has_any_role(user_roles: list, allowed_roles: set) -> bool:
    return bool(set(user_roles) & allowed_roles)


@router.post("/")
def create_stay(
    payload: StayRegistry,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """Create a new stay and register the guest if needed."""
    if Role.guest_relations_supervisor.value not in current_user.get("role", []):
        raise HTTPException(
            status_code=403,
            detail="Only users with guest relations supervisor roles can create stays.",
        )
    return add_new_stay(payload, current_user)


@router.patch("/{stay_id}")
def patch_stay(
    stay_id: int,
    payload: StayUpdate,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """
    Update a stay and its associated guest.

    Guest fields can only be updated if the guest is associated to this stay only.
    """
    if Role.guest_relations_supervisor.value not in current_user.get("role", []):
        raise HTTPException(
            status_code=403,
            detail="Only guest relations supervisors can update stays.",
        )
    updated_stay = update_stay(
        stay_id=stay_id,
        payload=payload,
        namespace_id=current_user["namespace_id"],
    )

    return ApiResponse(data=StayOrm(**updated_stay))


@router.get("/active")
def list_active_stays(
    db=Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """List all active stays where today is between start_date and end_date."""
    allowed_roles = {
        Role.guest_relations_supervisor.value,
        Role.supervisor.value,
        Role.admin.value,
        Role.owner.value,
    }
    if not _has_any_role(current_user.get("role", []), allowed_roles):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view stays.",
        )
    stays = get_active_stays(
        namespace_id=current_user["namespace_id"],
        db=db,
    )

    return ApiResponse(data=[StayOrm(**stay) for stay in stays])


@router.get("/{stay_id}")
def get_stay(
    stay_id: int,
    db=Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """Get a specific stay with its associated guest."""
    stay = get_stay_with_guest(
        stay_id=stay_id,
        namespace_id=current_user["namespace_id"],
        db=db,
    )
    return ApiResponse(data=stay)


@router.delete("/")
def delete(
    payload: DeleteStaysIn,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """Delete a list of stays by their IDs."""
    if Role.guest_relations_supervisor.value not in current_user.get("role", []):
        raise HTTPException(
            status_code=403,
            detail="Only guest relations supervisors can delete stays.",
        )
    deleted_count = delete_stays(
        stay_ids=payload.stay_ids,
        namespace_id=current_user["namespace_id"],
    )

    return ApiResponse(data={"deleted_count": deleted_count})
