from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app.globals.response import ApiResponse
from src.app.db.orm import get_db
from src.app.routers.namespace_settings.modelsIn import SettingsCreate, SettingsUpdate
from src.app.routers.namespace_settings.modelsOut import SettingsResponse
from src.app.routers.namespace_settings.services import (
    create_settings,
    get_settings,
    update_settings,
    check_user_permissions,
)
from src.app.globals.authentication import CurrentUserIdentifier


router = APIRouter(
    prefix="/namespace-settings",
    tags=["namespace-settings"],
)


@router.post("/create", response_model=ApiResponse)
def create_namespace_settings(
    settings: SettingsCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    """Create settings for a namespace"""
    check_user_permissions(current_user)

    result = create_settings(
        db=db, namespace_id=current_user["namespace_id"], settings=settings
    )
    return ApiResponse(data=SettingsResponse(**result).model_dump())


@router.get("/", response_model=ApiResponse)
def read_namespace_settings(
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    """Get settings for a namespace"""
    check_user_permissions(current_user)

    namespace_id = current_user["namespace_id"]
    settings = get_settings(namespace_id=namespace_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return ApiResponse(data=SettingsResponse(**settings).model_dump())


@router.patch("/{settings_id}", response_model=ApiResponse)
def update_namespace_settings(
    settings_id: int,
    settings: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    """Update settings for a namespace"""
    check_user_permissions(current_user)

    updated_settings = update_settings(
        db=db, settings_id=settings_id, settings=settings
    )
    if not updated_settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return ApiResponse(data=SettingsResponse(**updated_settings).model_dump())
