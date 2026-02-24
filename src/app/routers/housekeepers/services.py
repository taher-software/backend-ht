from fastapi import HTTPException, UploadFile, status
from src.app.resourcesController import housekeeper_controller
from src.app.globals.decorators import transactional
from src.app.db.models.housekeepers import Housekeeper
from src.app.gcp.gcs import storage_client
import tempfile
import os


def _upload_avatar(avatar: UploadFile) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_file = os.path.join(temp_dir, avatar.filename)
        with open(dest_file, "wb") as f:
            f.write(avatar.file.read())
        return storage_client.upload_to_bucket(
            "housekeeper_avatars", dest_file, avatar.filename
        )


def _get_or_404(housekeeper_id: int) -> dict:
    housekeeper = housekeeper_controller.find_by_id(housekeeper_id)
    if not housekeeper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Housekeeper with id {housekeeper_id} not found",
        )
    return housekeeper


def create_housekeeper(namespace_id: int, payload, avatar: UploadFile = None, db=None):
    data = payload.model_dump()
    data["namespace_id"] = namespace_id
    if avatar:
        data["avatar_url"] = _upload_avatar(avatar)
    return housekeeper_controller.create(data, db=db)


def update_housekeeper(
    housekeeper_id: int,
    namespace_id: int,
    payload,
    avatar: UploadFile = None,
    db=None,
):
    housekeeper = _get_or_404(housekeeper_id)
    if housekeeper["namespace_id"] != namespace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Housekeeper does not belong to your namespace",
        )
    data = payload.model_dump(exclude_unset=True)
    if avatar:
        data["avatar_url"] = _upload_avatar(avatar)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    return housekeeper_controller.update(housekeeper_id, data, db=db)


def delete_housekeeper(housekeeper_id: int, namespace_id: int):
    housekeeper = _get_or_404(housekeeper_id)
    if housekeeper["namespace_id"] != namespace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Housekeeper does not belong to your namespace",
        )
    housekeeper_controller.delete(housekeeper_id, db=housekeeper_controller.db)


def get_all_housekeepers(namespace_id: int, page: int, limit: int) -> dict:
    db = housekeeper_controller.db
    query = db.query(Housekeeper).filter(Housekeeper.namespace_id == namespace_id)
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [h.to_dict() for h in items],
    }


@transactional
def delete_housekeepers_batch(housekeeper_ids: list[int], namespace_id: int, db=None):
    for housekeeper_id in housekeeper_ids:
        housekeeper = _get_or_404(housekeeper_id)
        if housekeeper["namespace_id"] != namespace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Housekeeper with id {housekeeper_id} does not belong to your namespace",
            )
        housekeeper_controller.delete(housekeeper_id, commit=False, db=db)
    return len(housekeeper_ids)


def get_housekeeper(housekeeper_id: int, namespace_id: int) -> dict:
    housekeeper = _get_or_404(housekeeper_id)
    if housekeeper["namespace_id"] != namespace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Housekeeper does not belong to your namespace",
        )
    return housekeeper
