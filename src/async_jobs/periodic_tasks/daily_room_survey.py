from src.async_jobs import celery_app
from src.app.db.orm import get_db
from src.app.db.models import Namespace
from src.app.db.models import NamespaceSettings
from src.app.db.models import Stay
from src.app.db.models import Guest
from datetime import datetime, date
from zoneinfo import ZoneInfo
from datetime import timedelta
from sqlalchemy import and_
from src.settings import client
from src.app.globals.notification import send_push_notification
from functools import lru_cache


def get_concerned_namespaces():
    db_generator = get_db()
    db = next(db_generator)

    namespaces = (
        db.query(Namespace)
        .join(NamespaceSettings, Namespace.id == NamespaceSettings.namespace_id)
        .all()
    )

    results = []
    for ns in namespaces:
        tz = ZoneInfo(ns.timezone)
        survey_dt = datetime.combine(
            date.today(), ns.settings.room_survey_time, tzinfo=tz
        )
        now_tz = datetime.now(tz)
        if timedelta(0) <= (now_tz - survey_dt) < timedelta(minutes=600):
            results.append(ns.id)
    return results


def get_current_guest_for_given_namespace(namespace_id: int):
    db_generator = get_db()
    db = next(db_generator)
    guests_ids = (
        db.query(Stay.guest_id)
        .filter(
            and_(
                Stay.namespace_id == namespace_id,
                Stay.start_date <= datetime.today(),
                Stay.end_date >= datetime.today(),
            )
        )
        .all()
    )
    return guests_ids


def create_room_survey_notif_body(guest_name: str, language: str):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates short push notifications "
                    "for hotel guests in different languages. "
                    "The notification should ask the guest about their daily room satisfaction, "
                    "mention that the survey is inside the app."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification template in {language} for guest {guest_name}, "
                    "Use this example as structure:\n"
                    '"Hello {guest_name}, how was your room today? Let us know your satisfaction in the daily survey in the app."'
                ),
            },
        ],
    )
    return completion.choices[0].message.content


@lru_cache
def create_room_survey_notif_title(language: str):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates notification titles "
                    "for hotel guests in different languages. "
                    "The title should be tailored to the guest using their preferred language."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification title in {language}. "
                    "Use this example as structure:\n"
                    '"How Was Your Room Today?"'
                ),
            },
        ],
    )
    return completion.choices[0].message.content


def send_guest_room_survey_notif(guest_id: str):
    db_generator = get_db()
    db = next(db_generator)
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    notif_title = create_room_survey_notif_title(guest.pref_language)
    notif_body = create_room_survey_notif_body(guest.first_name, guest.pref_language)
    send_push_notification(guest.current_device_token, notif_title, notif_body)


@celery_app.task
def send_notif_daily_room_satisf():

    namespaces_ids = get_concerned_namespaces()
    if not namespaces_ids:
        return
    for ns_id in namespaces_ids:
        guests_ids = get_current_guest_for_given_namespace(ns_id)
        if not guests_ids:
            continue
        for g_id in guests_ids:
            send_guest_room_survey_notif(g_id)
