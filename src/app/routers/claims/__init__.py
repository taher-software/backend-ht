from src.app.globals.response import ApiResponse
from fastapi import (
    UploadFile,
    File,
    APIRouter,
    Body,
    Form,
    Depends,
    HTTPException,
    status,
    Path as pth,
)
from sqlalchemy import desc
from src.app.globals.generic_responses import validation_response
from .modelsIn import ClaimIn
from .services import (
    detect_language,
    define_category,
    transcript_audio,
    translate_text,
    country_mother_language,
    create_body_notif,
    create_title_notif,
    create_claim_title,
    add_guest_claims,
)
from pathlib import Path
import os
from src.app.gcp.gcs import storage_client
from src.app.db.models.claims import Claim
from src.app.resourcesController import claim_controller, namespace_controller
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.notification import send_push_notification
from src.app.globals.schema_models import role_categ_assoc
from src.app.db.orm import get_db
from src.app.db.models import Users, Stay
from sqlalchemy import desc, and_, or_, any_
from dotmap import DotMap
from datetime import datetime
from src.app.routers.claims.modelsOut import ClaimGI, ClaimDetails, ClaimDetailsResponse
from mutagen.mp3 import MP3
from fastapi import Query
from typing import Literal
from src.app.globals.schema_models import ClaimStatus
from sqlalchemy import func
from src.app.globals.decorators import transactional
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/claims", tags=["Claims"], responses={**validation_response})


@router.post("/create")
def create_claim(
    payload: ClaimIn | None = None,
    img_files: list[UploadFile] = File(None),
    vid_file: UploadFile = File(None),
    voice_file: UploadFile = File(None),
    current_guest: dict = Depends(CurrentUserIdentifier(who="guest")),
) -> ApiResponse:

    notif_body = add_guest_claims(
        payload, current_guest, img_files, voice_file, vid_file
    )
    print(f"notif body: {notif_body}")
    return ApiResponse(data=notif_body)


@router.get("/guest_claims")
def guest_current_stay_claims(
    current_guest: dict = Depends(CurrentUserIdentifier(who="guest")),
    db=Depends(get_db),
    page: int = Query(...),
    limit: int = Query(...),
) -> ApiResponse:

    current_stay = (
        db.query(Stay)
        .filter(Stay.guest_id == current_guest["phone_number"])
        .order_by(desc(Stay.start_date))
        .first()
    )

    today = datetime.now()

    if today >= current_stay.start_date and today <= current_stay.end_date:

        namespace_id = current_stay.namespace_id

        claims = (
            db.query(Claim)
            .filter(
                and_(
                    Claim.namespace_id == namespace_id,
                    Claim.guest_id == current_guest["phone_number"],
                )
            )
            .order_by(desc(Claim.created_at))
            .offset(page * limit)
            .limit(limit)
            .all()
        )

        return ApiResponse(
            data={
                "claims": [ClaimGI(**claim.to_dict()) for claim in claims],
                "total": len(claims),
            }
        )
    else:
        raise HTTPException(
            status.HTTP_417_EXPECTATION_FAILED,
            "Current Guest doesn't have any current stay ",
        )


@router.get("/claim_detail/{id}")
def get_claim_details(
    id: int = pth(...),
    current_guest: dict = Depends(CurrentUserIdentifier(who="any")),
    db=Depends(get_db),
) -> ClaimDetails:

    claim = (
        db.query(Claim)
        .options(selectinload(Claim.receiver))
        .options(selectinload(Claim.resolver))
        .get(id)
    )

    if "id" not in current_guest:

        if claim.guest_id != current_guest["phone_number"]:
            raise HTTPException(
                status.HTTP_406_NOT_ACCEPTABLE,
                f"The requested claim with id {id} doesn't belong to the current user ",
            )
    else:
        if claim.claim_category not in role_categ_assoc.get(current_guest["role"], []):
            raise HTTPException(
                status.HTTP_406_NOT_ACCEPTABLE,
                f"The requested claim with id {id} doesn't belong to the current user scope ",
            )

    return ClaimDetails.model_validate(claim)


@router.get("/claims_status_listing")
def get_claims_status_listing(
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    status: ClaimStatus = Query(...),
    page: int = Query(...),
    limit: int = Query(...),
    db=Depends(get_db),
) -> ApiResponse:

    today = datetime.now().date()
    query = (
        db.query(Claim)
        .filter(
            and_(
                Claim.status == status.value,
                Claim.namespace_id == current_user["namespace_id"],
                func.date(Claim.created_at) == today,
            )
        )
        .order_by(desc(Claim.created_at))
    )

    total = query.count()
    claims = query.offset(page * limit).limit(limit).all()

    return ApiResponse(
        data={
            "claims": [ClaimGI(**claim.to_dict()) for claim in claims],
            "total": total,
        }
    )


@router.patch("/{action}/{id}")
def update_claim(
    action: Literal["approve", "reject", "acknowledge", "resolve"],
    id: int,
    current_user: dict = Depends(CurrentUserIdentifier(who="any")),
    db=Depends(get_db),
) -> ApiResponse:
    action_map_assoc = {
        "approve": ClaimStatus.closed.value,
        "reject": ClaimStatus.rejected.value,
        "acknowledge": ClaimStatus.processing.value,
        "resolve": ClaimStatus.resolved.value,
    }
    payload = {"status": action_map_assoc[action]}
    claim = claim_controller.find_by_id(id)
    if not claim:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Claim with id {id} not found",
        )
    if action in ["acknowledge", "resolve"]:

        if "id" not in current_user:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only authenticated users can acknowledge or resolve claims",
            )
        # Get allowed categories for user's role
        allowed_categories = role_categ_assoc.get(current_user["role"], [])
        if claim["claim_category"] not in allowed_categories:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"User with role {current_user['role']} is not allowed to {action} claims in category {claim['claim_category']}",
            )
    if action in ["approve", "reject"]:
        if "id" in current_user:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only authenticated guests can approve or reject their claims",
            )
        if claim["guest_id"] != current_user["phone_number"]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only the guest who created the claim can approve or reject it",
            )

    if action == "approve" or action == "reject":
        if claim["status"] != ClaimStatus.resolved.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Claim can only be approved or rejected if it is in resolved status",
            )
        if action == "approve":
            payload["approve_claim_time"] = datetime.now()
        if action == "reject":
            payload["reject_claim_time"] = datetime.now()
    if action == "acknowledge":
        if claim["status"] != ClaimStatus.pending.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Claim can only be acknowledged if it is in pending status",
            )
        payload["acknowledged_employee_id"] = current_user["id"]
        payload["acknowledged_claim_time"] = datetime.now()
    if action == "resolve":
        if claim["status"] != ClaimStatus.processing.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Claim can only be resolved if it is in processing status",
            )
        payload["resolver_employee_id"] = current_user["id"]
        payload["resolve_claim_time"] = datetime.now()

    claim_controller.update(id, payload, db=db)

    return ApiResponse(data="Claim updated successfully")
