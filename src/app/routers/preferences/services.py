from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.app.db.models.guest import Guest
from src.app.db.models.users import Users
from src.app.globals.utils import LANG_MAP


def update_pref_language_service(current_user: dict, payload, db: Session):
    lang_code = payload.pref_lang.lower()
    lang_name = LANG_MAP.get(lang_code)
    if not lang_name:
        raise HTTPException(status_code=400, detail="Unsupported language code")
    # Try to update Users first
    user = (
        db.query(Users).filter(Users.id == current_user.get("id")).first()
        if current_user.get("id")
        else None
    )
    if user:
        user.pref_language = lang_name
        db.commit()
        return {"detail": f"User language updated to {lang_name}"}
    # Otherwise, update Guest
    guest = (
        db.query(Guest)
        .filter(Guest.phone_number == current_user.get("phone_number"))
        .first()
        if current_user.get("phone_number")
        else None
    )
    if guest:
        guest.pref_language = lang_name
        db.commit()
        return {"detail": f"Guest language updated to {lang_name}"}
    raise HTTPException(status_code=404, detail="User or guest not found")
