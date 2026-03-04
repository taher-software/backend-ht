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
    translate_text,
    country_mother_language,
    create_body_notif,
    create_title_notif,
    create_claim_title,
    add_guest_claims,
    create_resume_claim,
    update_claim_status,
    get_current_employee_claims,
    close_guest_claim,
)
from src.app.globals.utils import transcript_audio, transcribe_audio_from_gcs_link
from pathlib import Path
import os
from src.app.gcp.gcs import storage_client
from src.app.db.models.claims import Claim
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.notification import send_push_notification
from src.app.globals.schema_models import role_categ_assoc
from src.app.db.orm import get_db
from src.app.db.models import Users, Stay
from sqlalchemy import desc, and_, or_, any_
from dotmap import DotMap
from datetime import datetime
from src.app.routers.claims.modelsOut import (
    ClaimGI,
    ClaimDetails,
    ClaimDetailsResponse,
    ExtendedClaimDetails,
    ClaimWithRoom,
)
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

    today = datetime.now().date()

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
        )
        total_claims = claims.count()
        claims = claims.offset(page * limit).limit(limit).all()

        return ApiResponse(
            data={
                "claims": [ClaimGI(**claim.to_dict()) for claim in claims],
                "total": total_claims,
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
) -> ExtendedClaimDetails:

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
        roles = current_guest.get("role", [])
        if not roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Current user does not have a valid role",
            )
        categ_assoc = []
        for role in roles:
            categ_assoc.extend(role_categ_assoc.get(role, []))

        if claim.claim_category not in categ_assoc:
            raise HTTPException(
                status.HTTP_406_NOT_ACCEPTABLE,
                f"The requested claim with id {id} doesn't belong to the current user scope ",
            )

    # claim_details = ClaimDetails.model_validate(claim)
    extended_claim_details = ExtendedClaimDetails.model_validate(claim)
    if "id" in current_guest:
        claim_title = extended_claim_details.claim_title
        claim_text = extended_claim_details.claim_text
        claim_voice_url = claim.claim_voice_url
        if claim_title:
            claim_language = detect_language(claim_title)
            user_language = current_guest.get("pref_language")
            if claim_language != user_language:
                claim_resume = create_resume_claim(
                    claim_text, claim_voice_url, user_language
                )
                extended_claim_details.claim_summary = claim_resume
                # extended_claim_details.claim_title = translate_text(claim_title)

    return extended_claim_details


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


@router.get("/current_employes")
def current_employee_claims(
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    room_number: int | None = Query(None, description="Filter by room number"),
    created_at: Literal["asc", "desc"] = Query("desc", description="Sort order for created_at"),
    updated_at: Literal["asc", "desc"] = Query("desc", description="Sort order for updated_at"),
    status: ClaimStatus | None = Query(None, description="Filter by claim status"),
) -> ApiResponse:
    """
    Retrieve today's claims for the current employee's namespace.

    Returns a paginated list of claims with their associated room,
    filtered by room_number and status if provided,
    sorted by created_at and updated_at.
    """
    claims, total = get_current_employee_claims(
        current_user=current_user,
        page=page,
        page_size=page_size,
        room_number=room_number,
        created_at_sort=created_at,
        updated_at_sort=updated_at,
        claim_status=status,
        db=db,
    )

    return ApiResponse(
        data={
            "claims": [ClaimWithRoom.model_validate(claim) for claim in claims],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.patch("/close/{claim_id}")
def close_claim(
    claim_id: int = pth(...),
    current_guest: dict = Depends(CurrentUserIdentifier(who="guest")),
) -> ApiResponse:
    result = close_guest_claim(claim_id=claim_id, current_guest=current_guest)
    return ApiResponse(data=result)


@router.patch("/{action}/{id}")
def update_claim(
    action: Literal["approve", "reject", "acknowledge", "resolve"],
    id: int,
    current_user: dict = Depends(CurrentUserIdentifier(who="any")),
) -> ApiResponse:
    result = update_claim_status(action=action, claim_id=id, current_user=current_user)
    return ApiResponse(data=result)
