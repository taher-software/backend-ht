from src.app.resourcesController import dishes_controller
from src.app.db.models import Dishes
from .modelsIn import DishesIn
from .modelsOut import DishesOut
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import List
from src.app.gcp.gcs import storage_client


def create_dish(
    payload: DishesIn,
    db: Session,
    img_file: UploadFile = None,
    current_user: dict = None,
):
    data = payload.model_dump(exclude_unset=True)
    img_url = data.get("img_url")

    # Set namespace_id from current_user
    if current_user and "namespace_id" in current_user:
        data["namespace_id"] = current_user["namespace_id"]
    else:
        raise HTTPException(
            status_code=400, detail="namespace_id is required from current_user."
        )

    # Check for duplicate dish name in the same namespace
    existing = (
        db.query(Dishes)
        .filter(
            Dishes.namespace_id == data["namespace_id"],
            Dishes.name == data["name"],
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A dish with the name '{data['name']}' already exists in this namespace.",
        )

    if img_url:
        # Use the provided URL, ignore file if both are present
        data["img_url"] = str(img_url).strip()
    elif img_file:
        url = storage_client.upload_to_bucket(
            "dishes_image_files",
            img_file.file,
            img_file.filename,
        )
        data["img_url"] = url
    else:
        raise HTTPException(
            status_code=400,
            detail="Either img_url or img_file must be provided",
        )

    dish = dishes_controller.create(data, db, commit=True)
    return dish


def list_dishes(db: Session, current_user: dict, page: int = 0, limit: int = 10):
    # Use dishes_controller to get all dishes for the user's namespace
    namespace_id = current_user.get("namespace_id")
    return dishes_controller.get_all(
        namespace_id=namespace_id, limit=limit, offset=page * limit, total=True
    )


def get_dish(dish_id: int):
    dish = dishes_controller.find_by_id(dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    return dish


def update_dish(dish_id: int, payload: DishesIn, db: Session):
    updated = dishes_controller.update(dish_id, payload.dict(), db=db)
    return updated


def delete_dish(dish_id: int, db: Session):
    dishes_controller.delete(dish_id, db=db)
    return {"detail": "Dish deleted successfully"}


def patch_dish(
    dish_id: int,
    payload: DishesIn,
    db: Session,
    img_file: UploadFile = None,
    current_user: dict = None,
):
    data = payload.model_dump(exclude_unset=True)
    # Only allow patching within user's namespace
    if current_user and "namespace_id" in current_user:
        data["namespace_id"] = current_user["namespace_id"]
    else:
        raise HTTPException(
            status_code=400, detail="namespace_id is required from current_user."
        )

    # Prevent updating to a name that already exists in another row
    if "name" in data:
        existing = (
            db.query(Dishes)
            .filter(
                Dishes.namespace_id == data["namespace_id"],
                Dishes.name == data["name"],
                Dishes.id != dish_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"A dish with the name '{data['name']}' already exists in this namespace.",
            )

    # If img_file is provided and img_url is not, upload and update img_url
    if not data.get("img_url") and img_file:
        url = storage_client.upload_to_bucket(
            "dishes_image_files",
            img_file.file,
            img_file.filename,
        )
        data["img_url"] = url
    # If both img_url and img_file are provided, use img_url (do nothing)
    # If only img_url is provided, use it (do nothing)
    # If neither, do nothing (partial update)

    updated = dishes_controller.update(dish_id, data, db=db)
    return updated
