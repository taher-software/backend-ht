import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import backoff

from src.app.db.models import Namespace
from src.app.db.orm import get_db
from zoneinfo import ZoneInfo
from datetime import datetime, date
from datetime import timedelta
from src.app.db.models import Stay
from sqlalchemy import and_
from src.app.gcp import firestore_client
from src.settings import client, settings

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "english"


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


# ---- Shared LLM translation helpers ----------------------------------------

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def _translate_template(source: dict, target_language: str) -> dict:
    """Translate a dict of template strings into target_language.
    Placeholders in `{braces}` MUST be preserved verbatim.
    """
    payload = json.dumps(source, ensure_ascii=False)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You translate JSON objects of notification/email "
                    "templates. Rules: (1) translate ONLY the natural-language "
                    "text; (2) keep every {placeholder_token} exactly as-is "
                    "(same spelling, same braces); (3) preserve HTML tags and "
                    "attributes unchanged; (4) return ONLY the translated "
                    "JSON object with the same keys."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target language: {target_language}.\n"
                    f"Source JSON:\n{payload}"
                ),
            },
        ],
    )
    raw = completion.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


def _load_or_translate(
    collection_name: str, source: dict, language: str
) -> dict:
    language = (language or DEFAULT_LANGUAGE).lower()
    if language == DEFAULT_LANGUAGE:
        return source
    cached = firestore_client.find_document(
        collection_name=collection_name,
        params={"language": language},
    )
    if cached:
        return {k: cached.get(k) for k in source.keys()}

    translated = _translate_template(source, language)
    firestore_client.create_document(
        collection_name=collection_name,
        data={"language": language, **translated},
    )
    return translated


# ---- Shared email sender ----------------------------------------------------

def _send_email(to_email: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Bodor <{settings.mail_username}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(settings.mail_username, settings.mail_pwd)
        smtp.sendmail(settings.mail_username, to_email, msg.as_string())
