from fastapi import HTTPException, UploadFile, status
from src.app.resourcesController import guest_controller
from src.app.globals.utils import LANG_MAP
from src.app.gcp.gcs import storage_client
import tempfile
import os

GUESTS_AVATAR_BUCKET = "guests_avatar"


def update_guest_full_profile(payload, current_user: dict, avatar: UploadFile, db):
    lang_name = LANG_MAP.get(payload.pref_language.lower())
    if not lang_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported language code",
        )

    update_data = dict(
        first_name=payload.first_name,
        last_name=payload.last_name,
        current_device_token=payload.current_device_token,
        pref_language=lang_name,
        birth_date=payload.birth_date,
        nationality=payload.nationality,
        country_of_residence=payload.country_of_residence,
    )

    if avatar:
        with tempfile.TemporaryDirectory() as temp_dir:
            dest_file = os.path.join(temp_dir, avatar.filename)
            with open(dest_file, "wb") as f:
                f.write(avatar.file.read())
            avatar_url = storage_client.upload_to_bucket(
                GUESTS_AVATAR_BUCKET, dest_file, avatar.filename
            )
        update_data["avatar_url"] = avatar_url

    guest_controller.update(
        current_user["phone_number"],
        update_data,
        resource_key="phone_number",
        db=db,
    )


def update_guest_avatar(current_user: dict, avatar: UploadFile, db):
    guest = guest_controller.find_by_id(current_user["phone_number"])

    existing_url = guest.get("avatar_url") if guest else None
    if existing_url and f"storage.googleapis.com/{GUESTS_AVATAR_BUCKET}/" in existing_url:
        blob_name = existing_url.split(f"storage.googleapis.com/{GUESTS_AVATAR_BUCKET}/", 1)[1]
        storage_client.delete_from_bucket(GUESTS_AVATAR_BUCKET, blob_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        dest_file = os.path.join(temp_dir, avatar.filename)
        with open(dest_file, "wb") as f:
            f.write(avatar.file.read())
        new_avatar_url = storage_client.upload_to_bucket(
            GUESTS_AVATAR_BUCKET, dest_file, avatar.filename
        )

    guest_controller.update(
        current_user["phone_number"],
        dict(avatar_url=new_avatar_url),
        resource_key="phone_number",
        db=db,
    )
