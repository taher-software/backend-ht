from fastapi import APIRouter, Depends
from src.app.db.orm import get_db
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from .modelsIn import ReviewAccount
from .modelsOut import (
    namespace_not_found_response,
    user_not_found_response,
    user_namespace_mismatch_response,
)
from .services import handle_approve_account, handle_reject_account

router = APIRouter(
    prefix="/super_admin", tags=["Super_Admin"], responses={**validation_response}
)


@router.patch(
    "/approve_account",
    response_model=ApiResponse,
    description="Approve a pending account and send verification email to the owner",
    responses={
        **namespace_not_found_response,
        **user_not_found_response,
        **user_namespace_mismatch_response,
    },
)
def approve_account(payload: ReviewAccount, db=Depends(get_db)) -> ApiResponse:
    result = handle_approve_account(
        hotel_name=payload.hotel_name,
        user_email=payload.user_email,
        country=payload.country,
        city=payload.city,
        db=db,
    )
    return ApiResponse(data=result["data"])


@router.patch(
    "/reject_account",
    response_model=ApiResponse,
    description="Reject a pending account, send rejection email, and delete namespace",
    responses={
        **namespace_not_found_response,
        **user_not_found_response,
        **user_namespace_mismatch_response,
    },
)
def reject_account(payload: ReviewAccount, db=Depends(get_db)) -> ApiResponse:
    result = handle_reject_account(
        hotel_name=payload.hotel_name,
        user_email=payload.user_email,
        country=payload.country,
        city=payload.city,
        db=db,
    )
    return ApiResponse(data=result["data"])
