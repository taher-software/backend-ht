from fastapi import (
    APIRouter,
    Depends,
    Body,
    UploadFile,
    File,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session
from src.app.globals.response import ApiResponse
from src.app.db.orm import get_db
from src.app.globals.authentication import CurrentUserIdentifier
from .modelsIn import DishesIn, DishesUpdate
from .modelsOut import DishesOut, DishesListOut
from . import services
from typing import List
from src.app.globals.schema_models import Role
from src.app.globals.generic_responses import validation_response

router = APIRouter(prefix="/dishes", tags=["dishes"], responses={**validation_response})


@router.post("/", response_model=DishesOut)
def create_dish(
    payload: DishesIn = Body(...),
    img_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):

    allowed_roles = {
        Role.owner.value,
        Role.admin.value,
        Role.supervisor.value,
        Role.dining_supervisor.value,
    }
    if not set(current_user.get("role", [])) & allowed_roles:
        raise HTTPException(
            status_code=403, detail="You do not have permission to create dishes."
        )
    return services.create_dish(payload, db, img_file, current_user)


@router.get("/", response_model=DishesListOut)
def list_dishes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
    page: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    allowed_roles = {
        Role.owner.value,
        Role.admin.value,
        Role.supervisor.value,
        Role.dining_supervisor.value,
    }
    if not set(current_user.get("role", [])) & allowed_roles:
        raise HTTPException(
            status_code=403, detail="You do not have permission to list dishes."
        )
    return services.list_dishes(db, current_user, page, limit)


@router.get("/{dish_id}", response_model=ApiResponse)
def get_dish(
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    allowed_roles = {
        Role.owner.value,
        Role.admin.value,
        Role.supervisor.value,
        Role.dining_supervisor.value,
    }
    if not set(current_user.get("role", [])) & allowed_roles:
        raise HTTPException(
            status_code=403, detail="You do not have permission to get dishes."
        )
    return ApiResponse(data=services.get_dish(dish_id))


@router.patch("/{dish_id}", response_model=DishesOut)
def patch_dish(
    dish_id: int,
    payload: DishesUpdate = Body(...),
    img_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    allowed_roles = {
        Role.owner.value,
        Role.admin.value,
        Role.supervisor.value,
        Role.dining_supervisor.value,
    }
    if not set(current_user.get("role", [])) & allowed_roles:
        raise HTTPException(
            status_code=403, detail="You do not have permission to update dishes."
        )
    return services.patch_dish(dish_id, payload, db, img_file, current_user)


@router.delete("/{dish_id}")
def delete_dish(
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    allowed_roles = {
        Role.owner.value,
        Role.admin.value,
        Role.supervisor.value,
        Role.dining_supervisor.value,
    }
    if not set(current_user.get("role", [])) & allowed_roles:
        raise HTTPException(
            status_code=403, detail="You do not have permission to delete dishes."
        )
    return services.delete_dish(dish_id, db)
