from fastapi import APIRouter, Depends, Body
from src.app.db.orm import get_db
from src.app.globals.authentication import CurrentUserIdentifier
from .modelsIn import PrefLangUpdateIn
from .services import update_pref_language_service

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.patch("/update_pref_language")
def update_pref_language_endpoint(
    payload: PrefLangUpdateIn = Body(...),
    db=Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="any")),
):
    """Update preferred language for current user (user or guest)"""
    return update_pref_language_service(current_user, payload, db)
