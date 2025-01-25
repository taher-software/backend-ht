from app.globals.response import ApiResponse
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
from app.globals.generic_responses import validation_response
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
)
from pathlib import Path
import os
from app.gcp.gcs import storage_client
from app.db.models.claims import Claim
from app.resourcesController import claim_controller, namespace_controller
from app.globals.authentication import CurrentUserIdentifier
from app.globals.notification import send_push_notification
from app.globals.schema_models import role_categ_assoc
from app.db.orm import get_db
from app.db.models import Users, Stay
from sqlalchemy import desc, and_, or_, any_
from dotmap import DotMap
from datetime import datetime
from app.routers.claims.modelsOut import ClaimGI, ClaimDetails, ClaimDetailsResponse
from mutagen.mp3 import MP3

router = APIRouter(prefix="/claims", tags=["Claims"], responses={**validation_response})
destination_path = Path(__file__).parent


@router.post("/create")
def create_claim(
    payload: ClaimIn | None = None,
    img_files: list[UploadFile] = File(None),
    vid_file: UploadFile = File(None),
    voice_file: UploadFile = File(None),
    current_guest: dict = Depends(CurrentUserIdentifier(who="guest")),
    db=Depends(get_db),
) -> ApiResponse:

    guest = DotMap(current_guest)
    claim_dict = dict(guest_id=guest.phone_number)

    if payload and payload.text:
        claim_text = payload.text
        claim_language = detect_language(claim_text)
        claim_category = define_category(claim_text)
        claim_dict.update(
            dict(
                claim_text=claim_text,
                claim_language=claim_language,
                claim_category=claim_category,
            )
        )
    if img_files:
        img_urls = []
        for img in img_files:
            destination_file = os.path.join(destination_path, img.filename)
            with open(destination_file, "wb") as f:
                f.write(img.file.read())
            img_url = storage_client.upload_to_bucket(
                "book-management-api-58a60.appspot.com",
                destination_file,
                f"image_claim_files/{img.filename}",
            )
            img_urls.append(img_url)
            os.remove(destination_file)
        claim_dict.update(dict(claim_images_url=img_urls))
    if vid_file:
        destination_file = os.path.join(destination_path, vid_file.filename)
        with open(destination_file, "wb") as f:
            f.write(vid_file.file.read())
        vid_url = storage_client.upload_to_bucket(
            "book-management-api-58a60.appspot.com",
            destination_file,
            f"video_claim_files/{vid_file.filename}",
        )
        os.remove(destination_file)
        claim_dict.update(dict(claim_video_url=vid_url))
    if voice_file:
        print("voice file received")
        destination_file = os.path.join(destination_path, voice_file.filename)
        with open(destination_file, "wb") as f:
            f.write(voice_file.file.read())

        claim_text = transcript_audio(destination_file)
        claim_language = detect_language(claim_text)
        claim_category = define_category(claim_text)
        voice_url = storage_client.upload_to_bucket(
            "book-management-api-58a60.appspot.com",
            destination_file,
            f"voice_claim_files/{voice_file.filename}",
        )

        os.remove(destination_file)
        claim_dict.update(
            dict(
                claim_voice_url=voice_url,
                claim_category=claim_category,
                claim_language=claim_language,
                claim_voice_duration=payload.voice_duration,
            )
        )
    else:
        print("no voice file received...")
    claim_title = create_claim_title(claim_text, claim_language)
    claim_dict.update(dict(claim_title=claim_title))

    stay = (
        db.query(Stay)
        .filter(Stay.guest_id == guest.phone_number)
        .order_by(desc(Stay.start_date))
        .first()
    )

    claim_dict.update(dict(namespace_id=stay.namespace_id))
    claim_dict.update(dict(stay_id=stay.id))

    claim_controller.create(claim_dict)

    role = role_categ_assoc[claim_category]

    employees = (
        db.query(Users)
        .filter(
            and_(
                Users.namespace_id == stay.namespace_id,
                or_(
                    Users.role.contains(role),
                    Users.role.contains("supervisor"),
                ),
            )
        )
        .all()
    )
    namespace = namespace_controller.find_by_id(stay.namespace_id)
    namespace = DotMap(namespace)
    country = namespace.country
    namespace_language = country_mother_language(country)
    print(f"namespace language: {namespace_language}")
    notif_title = create_title_notif(namespace_language)
    print(f"notif title: {notif_title}")
    notif_body = create_body_notif(claim_text, namespace_language, stay.stay_room)
    print(f"notif title: {notif_body}")

    # review the case with unknown type
    for emp in employees:

        send_push_notification(emp.current_device_token, notif_title, notif_body)
    return ApiResponse(data=notif_body)


@router.get("/guest_claims")
def guest_current_stay_claims(
    current_guest: dict = Depends(CurrentUserIdentifier(who="guest")),
    db=Depends(get_db),
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
            .all()
        )

        return ApiResponse(data=[ClaimGI(**claim.to_dict()) for claim in claims])
    else:
        raise HTTPException(
            status.HTTP_417_EXPECTATION_FAILED,
            "Current Guest doesn't have any current stay ",
        )


@router.get("/claim_detail/{id}")
def get_claim_details(
    id: int = pth(...),
    current_guest: dict = Depends(CurrentUserIdentifier(who="guest")),
    db=Depends(get_db),
) -> ClaimDetails:

    claim = claim_controller.find_by_id(id)
    if claim["guest_id"] != current_guest["phone_number"]:
        raise HTTPException(
            status.HTTP_406_NOT_ACCEPTABLE,
            f"The requested claim with id {id} doesn't belong to the current user ",
        )

    return ClaimDetails(**claim)
