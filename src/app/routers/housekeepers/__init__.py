from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from src.app.globals.schema_models import Role
from .modelsIn import HousekeeperCreateIn, HousekeeperUpdateIn, DeleteHousekeepersBatchIn
from .modelsOut import HousekeeperOut
from . import services

router = APIRouter(
    prefix="/housekeepers",
    tags=["Housekeepers"],
    responses={**validation_response},
)

ALLOWED_ROLES = {
    Role.owner.value,
    Role.admin.value,
    Role.supervisor.value,
    Role.housekeeping_supervisor.value,
}


def _check_role(current_user: dict):
    if not set(current_user.get("role", [])) & ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage housekeepers.",
        )


@router.post("/", response_model=ApiResponse)
def create_housekeeper(
    payload: HousekeeperCreateIn,
    avatar: UploadFile = File(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """Create a new housekeeper."""
    _check_role(current_user)
    housekeeper = services.create_housekeeper(
        namespace_id=current_user["namespace_id"],
        payload=payload,
        avatar=avatar,
    )
    return ApiResponse(data=HousekeeperOut(**housekeeper).model_dump())


@router.patch("/{housekeeper_id}", response_model=ApiResponse)
def update_housekeeper(
    housekeeper_id: int,
    payload: HousekeeperUpdateIn,
    avatar: UploadFile = File(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """Update a housekeeper's details."""
    _check_role(current_user)
    housekeeper = services.update_housekeeper(
        housekeeper_id=housekeeper_id,
        namespace_id=current_user["namespace_id"],
        payload=payload,
        avatar=avatar,
    )
    return ApiResponse(data=HousekeeperOut(**housekeeper).model_dump())


@router.delete("/{housekeeper_id}", response_model=ApiResponse)
def delete_housekeeper(
    housekeeper_id: int,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """Delete a specific housekeeper by ID."""
    _check_role(current_user)
    services.delete_housekeeper(
        housekeeper_id=housekeeper_id,
        namespace_id=current_user["namespace_id"],
    )
    return ApiResponse(data="Housekeeper deleted successfully.")


@router.get("/", response_model=ApiResponse)
def list_housekeepers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """List all housekeepers for the current namespace, paginated."""
    _check_role(current_user)
    result = services.get_all_housekeepers(
        namespace_id=current_user["namespace_id"],
        page=page,
        limit=limit,
    )
    return ApiResponse(data={
        "total": result["total"],
        "page": result["page"],
        "limit": result["limit"],
        "items": [HousekeeperOut(**h).model_dump() for h in result["items"]],
    })


@router.delete("/", response_model=ApiResponse)
def delete_housekeepers_batch(
    payload: DeleteHousekeepersBatchIn,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """Delete multiple housekeepers by a list of IDs."""
    _check_role(current_user)
    deleted_count = services.delete_housekeepers_batch(
        housekeeper_ids=payload.housekeeper_ids,
        namespace_id=current_user["namespace_id"],
    )
    return ApiResponse(data={"deleted_count": deleted_count})


@router.get("/{housekeeper_id}", response_model=ApiResponse)
def get_housekeeper(
    housekeeper_id: int,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """Get a specific housekeeper by ID."""
    _check_role(current_user)
    housekeeper = services.get_housekeeper(
        housekeeper_id=housekeeper_id,
        namespace_id=current_user["namespace_id"],
    )
    return ApiResponse(data=HousekeeperOut(**housekeeper).model_dump())
