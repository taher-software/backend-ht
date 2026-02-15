from src.app.db.models import Namespace
from src.app.db.orm import get_db
from zoneinfo import ZoneInfo
from datetime import datetime, date
from datetime import timedelta
from src.app.db.models import Stay
from sqlalchemy import and_


def get_concerned_namespaces(survey_time_field: str = "room_survey_time", db=None):
    if db is None:
        raise ValueError("Database session must be provided")
    namespaces = db.query(Namespace).all()
    results = []
    for ns in namespaces:
        if not ns.settings:
            continue  # skip if no settings
        tz = ZoneInfo(ns.timezone)
        survey_dt = datetime.combine(
            date.today(), getattr(ns.settings, survey_time_field), tzinfo=tz
        )
        now_tz = datetime.now(tz)
        if timedelta(0) <= (now_tz - survey_dt) < timedelta(minutes=60):
            results.append(ns.id)
    return results


def get_current_guest_for_given_namespace(
    namespace_id: int, check_meal_eligibility: bool = False, db=None
):
    if db is None:
        raise ValueError("Database session must be provided")
    guests_ids = db.query(Stay.guest_id).filter(
        and_(
            Stay.namespace_id == namespace_id,
            Stay.start_date < datetime.today(),
            Stay.end_date > datetime.today(),
        )
    )
    if check_meal_eligibility:
        guests_ids = guests_ids.filter(Stay.meal_plan != "EP")

    # Return list of guest_id strings, not Row objects
    result = guests_ids.all()
    return [row[0] for row in result]
