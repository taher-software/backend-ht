from fastapi import APIRouter, Depends, HTTPException
from src.app.globals.response import ApiResponse
from src.app.globals.generic_responses import validation_response
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.schema_models import Role
from .modelsIn import CreatePlanIn
from .services import create_plan

router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"],
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
            detail="You do not have permission to manage assignments.",
        )


@router.post("/plan")
def create_plan_endpoint(
    payload: CreatePlanIn,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    _check_role(current_user)
    create_plan(
        namespace_id=current_user["namespace_id"],
        plan_date=payload.date,
        assignments=payload.assignments,
    )
    return ApiResponse(data="Plan created successfully.")
