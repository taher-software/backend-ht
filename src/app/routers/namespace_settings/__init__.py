from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.app.db.orm import get_db
from src.app.routers.namespace_settings.modelsIn import SettingsCreate, SettingsUpdate
from src.app.routers.namespace_settings.modelsOut import SettingsResponse
from src.app.routers.namespace_settings.services import (
    create_settings,
    get_settings,
    update_settings,
)
from src.app.globals.schema_models import Role, role_categ_assoc
from src.app.globals.authentication import CurrentUserIdentifier
from .services import check_user_permissions


router = APIRouter(
    prefix="/namespace-settings",
    tags=["namespace-settings"],
)


@router.post("/create", response_model=SettingsResponse)
def create_namespace_settings(
    settings: SettingsCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    """Create settings for a namespace"""
    # Check user permissions
    check_user_permissions(current_user)

    return create_settings(
        db=db, namespace_id=current_user["namespace_id"], settings=settings
    )


@router.get("/{namespace_id}", response_model=SettingsResponse)
def read_namespace_settings(
    namespace_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):

    # Check user permissions
    check_user_permissions(current_user)

    """Get settings for a namespace"""
    settings = get_settings(namespace_id=namespace_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return SettingsResponse(**settings)


@router.patch("/{settings_id}", response_model=SettingsResponse)
def update_namespace_settings(
    settings_id: int,
    settings: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    """Update settings for a namespace"""
    # Check user permissions
    check_user_permissions(current_user)
    updated_settings = update_settings(
        db=db, settings_id=settings_id, settings=settings
    )
    if not updated_settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return updated_settings
