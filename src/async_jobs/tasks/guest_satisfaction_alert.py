import logging

import backoff
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from src.app.db.orm import get_db
from src.app.db.models import Users, Stay, Guest, Namespace
from src.app.db.models.claims import Claim
from src.app.db.models.daily_room_sat_survey import DailyRoomSatisfactionSurvey
from src.app.db.models.room_reception_survey import RoomReceptionSurvey
from src.app.db.models.daily_restaurant_survey import DailyRestaurantSurvey
from src.app.globals.enum import (
    CachingCollectionName,
    ClaimCriticality,
)
from src.app.globals.notification import send_push_notification
from src.app.globals.schema_models import Role
from src.async_jobs.tasks.utils import (
    DEFAULT_LANGUAGE,
    _load_or_translate,
    _send_email,
)

logger = logging.getLogger(__name__)


# ---- Standard English templates (source of truth for all languages) --------

PUSH_TEMPLATE_EN = {
    "title": "⚠️ Guest Satisfaction Alert — Room {room_number}",
    "body": (
        "Guest {guest_name} in room {room_number} ({area}) is at "
        "{score} satisfaction. Check your email and act now."
    ),
}

EMAIL_TEMPLATE_EN = {
    "subject": (
        "Urgent: Guest satisfaction dropped below target — {namespace_name}"
    ),
    "body_html": (
        "<html><body style=\"font-family:Arial,sans-serif;color:#222;\">"
        "<h2 style=\"color:#c0392b;\">⚠️ Guest satisfaction alert</h2>"
        "<p>Dear team at <strong>{namespace_name}</strong>,</p>"
        "<p>Guest <strong>{guest_name}</strong> in room "
        "<strong>{room_number}</strong> ({area}) has a current satisfaction "
        "of <strong>{score}</strong>, which is below your target "
        "satisfaction of <strong>{target_satisfaction}</strong>.</p>"
        "<p>The guest is still at the hotel. Please act now to recover "
        "the stay and prevent a negative public review.</p>"
        "<h3>Context for this stay</h3>"
        "<ul>"
        "<li>Claims: {high_claims} high, {medium_claims} medium, "
        "{low_claims} low</li>"
        "<li>Room reception low-score items: {room_reception_low}</li>"
        "<li>Daily room low-score items: {daily_room_low}</li>"
        "<li>Restaurant low-score items: {restaurant_low}</li>"
        "<li>Restaurant queue encounters: {queue_encounters}</li>"
        "</ul>"
        "<p>— Bodor</p>"
        "</body></html>"
    ),
}


# ---- Context computation ---------------------------------------------------

def _percent(value: float) -> str:
    return f"{int(round((value or 0) * 100))}%"


def _compute_context(db, stay: Stay, guest: Guest, namespace: Namespace) -> dict:
    claims = db.query(Claim).filter(Claim.stay_id == stay.id).all()
    high = sum(
        1 for c in claims if c.criticality == ClaimCriticality.high.value
    )
    medium = sum(
        1 for c in claims if c.criticality == ClaimCriticality.medium.value
    )
    low = sum(
        1 for c in claims if c.criticality == ClaimCriticality.low.value
    )

    rr_surveys = (
        db.query(RoomReceptionSurvey)
        .filter(
            RoomReceptionSurvey.stay_id == stay.id,
            RoomReceptionSurvey.namespace_id == namespace.id,
        )
        .all()
    )
    room_reception_low = sum(
        1 for s in rr_surveys for v in [s.Q1, s.Q2, s.Q3, s.Q4]
        if v is not None and v < 2.5
    )

    dr_surveys = (
        db.query(DailyRoomSatisfactionSurvey)
        .filter(
            DailyRoomSatisfactionSurvey.stay_id == stay.id,
            DailyRoomSatisfactionSurvey.namespace_id == namespace.id,
        )
        .all()
    )
    daily_room_low = sum(
        1 for s in dr_surveys for v in [s.Q1, s.Q2, s.Q3, s.Q4]
        if v is not None and v < 2.5
    )

    rest_surveys = (
        db.query(DailyRestaurantSurvey)
        .filter(
            DailyRestaurantSurvey.stay_id == stay.id,
            DailyRestaurantSurvey.namespace_id == namespace.id,
        )
        .all()
    )
    restaurant_low = 0
    for s in rest_surveys:
        for v in [s.Q1, s.Q2, s.Q3]:
            if v is not None and v < 2.5:
                restaurant_low += 1
    queue_encounters = sum(1 for s in rest_surveys if s.Q4 == 1)

    guest_name = (
        f"{guest.first_name or ''} {guest.last_name or ''}".strip()
        or guest.phone_number
    )
    room_number = str(stay.room.room_number) if stay.room else "N/A"
    area = (stay.room.area if stay.room else None) or "Main"

    target_raw = (
        namespace.settings.satisfaction_threshold
        if namespace.settings is not None
        and namespace.settings.satisfaction_threshold is not None
        else 0.5
    )

    return {
        "guest_name": guest_name,
        "room_number": room_number,
        "area": area,
        "score": _percent(stay.guest_satisfaction),
        "target_satisfaction": _percent(target_raw),
        "namespace_name": namespace.hotel_name or "",
        "high_claims": str(high),
        "medium_claims": str(medium),
        "low_claims": str(low),
        "room_reception_low": str(room_reception_low),
        "daily_room_low": str(daily_room_low),
        "restaurant_low": str(restaurant_low),
        "queue_encounters": str(queue_encounters),
    }


def _format(template: str, context: dict) -> str:
    try:
        return template.format(**context)
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"Template formatting skipped: {e}")
        return template



# ---- Handler ---------------------------------------------------------------

RECIPIENT_ROLES = [
    Role.owner.value,
    Role.supervisor.value,
    Role.guest_relations_supervisor.value,
]


@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def send_satisfaction_alert(
    namespace_id: int,
    job_id: str,
    payload: dict = None,
    **kwargs,
) -> dict:
    payload = payload or {}
    stay_id = payload.get("stay_id")
    guest_id = payload.get("guest_id")
    if stay_id is None or guest_id is None:
        raise ValueError(
            f"[Job {job_id}] Missing stay_id/guest_id in payload: {payload}"
        )

    db_gen = get_db()
    db = next(db_gen)
    try:
        stay = (
            db.query(Stay)
            .options(selectinload(Stay.room))
            .filter(Stay.id == stay_id)
            .first()
        )
        if not stay:
            raise ValueError(f"Stay {stay_id} not found")

        guest = db.query(Guest).filter(Guest.phone_number == guest_id).first()
        if not guest:
            raise ValueError(f"Guest {guest_id} not found")

        namespace = (
            db.query(Namespace)
            .options(selectinload(Namespace.settings))
            .filter(Namespace.id == namespace_id)
            .first()
        )
        if not namespace:
            raise ValueError(f"Namespace {namespace_id} not found")

        role_filters = [Users.role.contains([r]) for r in RECIPIENT_ROLES]
        recipients = (
            db.query(Users)
            .filter(Users.namespace_id == namespace_id, or_(*role_filters))
            .all()
        )
        if not recipients:
            logger.info(
                f"[Job {job_id}] No eligible recipients for namespace "
                f"{namespace_id}, skipping"
            )
            return {
                "sent": 0,
                "namespace_id": namespace_id,
                "stay_id": stay_id,
            }

        context = _compute_context(db, stay, guest, namespace)

        by_lang: dict = {}
        for r in recipients:
            lang = (r.pref_language or DEFAULT_LANGUAGE).lower()
            by_lang.setdefault(lang, []).append(r)

        push_by_lang = {}
        email_by_lang = {}
        for lang in by_lang:
            try:
                push_by_lang[lang] = _load_or_translate(
                    CachingCollectionName.GUEST_SATISFACTION_NOTIF_TEMPLATES,
                    PUSH_TEMPLATE_EN,
                    lang,
                )
            except Exception as e:
                logger.error(
                    f"[Job {job_id}] Push template translate failed "
                    f"({lang}) — falling back to English: {e}"
                )
                push_by_lang[lang] = PUSH_TEMPLATE_EN
            try:
                email_by_lang[lang] = _load_or_translate(
                    CachingCollectionName.GUEST_SATISFACTION_EMAIL_TEMPLATES,
                    EMAIL_TEMPLATE_EN,
                    lang,
                )
            except Exception as e:
                logger.error(
                    f"[Job {job_id}] Email template translate failed "
                    f"({lang}) — falling back to English: {e}"
                )
                email_by_lang[lang] = EMAIL_TEMPLATE_EN

        sent = 0
        for lang, users in by_lang.items():
            push_tpl = push_by_lang[lang]
            email_tpl = email_by_lang[lang]
            push_title = _format(push_tpl["title"], context)
            push_body = _format(push_tpl["body"], context)
            email_subject = _format(email_tpl["subject"], context)
            email_body = _format(email_tpl["body_html"], context)

            for user in users:
                if user.current_device_token:
                    try:
                        send_push_notification(
                            user.current_device_token,
                            push_title,
                            push_body,
                            "urgent",
                        )
                    except Exception as e:
                        logger.error(
                            f"[Job {job_id}] Push failed user={user.id}: {e}"
                        )
                if user.user_email:
                    try:
                        _send_email(
                            user.user_email, email_subject, email_body
                        )
                    except Exception as e:
                        logger.error(
                            f"[Job {job_id}] Email failed user={user.id}: {e}"
                        )
                sent += 1

        logger.info(
            f"[Job {job_id}] Sent satisfaction alert to {sent} recipient(s) "
            f"for stay={stay_id} namespace={namespace_id}"
        )
        return {
            "sent": sent,
            "namespace_id": namespace_id,
            "stay_id": stay_id,
        }
    finally:
        try:
            db.close()
        except Exception as e:
            logger.error(f"[Job {job_id}] DB close error: {e}")
