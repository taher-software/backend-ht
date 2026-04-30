import logging
from datetime import datetime, timedelta, date, timezone as dt_timezone
from zoneinfo import ZoneInfo

import backoff
from sqlalchemy import func, and_, extract, or_
from sqlalchemy.orm import Session

from src.app.db.models import Users, Namespace
from src.app.db.models.claims import Claim
from src.app.db.models.daily_room_sat_survey import DailyRoomSatisfactionSurvey
from src.app.db.models.room_reception_survey import RoomReceptionSurvey
from src.app.db.models.daily_restaurant_survey import DailyRestaurantSurvey
from src.app.db.models.dishes_survey import DishesSurvey
from src.app.db.models.dishes import Dishes
from src.app.db.models.menu import Menu
from src.app.db.models.meals import Meal
from src.app.db.orm import get_db
from src.app.globals.enum import CachingCollectionName, JobType
from src.app.globals.schema_models import ClaimStatus, ClaimCategory, Role
from src.async_jobs.tasks.utils import (
    DEFAULT_LANGUAGE,
    _load_or_translate,
    _send_email,
)

logger = logging.getLogger(__name__)

RECIPIENT_ROLES = [Role.owner.value, Role.supervisor.value]

# ---- English source template ------------------------------------------------

EMAIL_TEMPLATE_EN = {
    "subject": "{namespace_name} — Daily Performance Report — {report_date}",
    "body_html": (
        "<html><body style='font-family:Arial,sans-serif;color:#222;max-width:680px;margin:0 auto;'>"
        "<h2 style='color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:8px;'>"
        "Daily Performance Report — {report_date}"
        "</h2>"
        "<p>Dear team at <strong>{namespace_name}</strong>,</p>"
        "<p>Here is the service performance summary for yesterday.</p>"

        "<h3 style='color:#2c3e50;'>Claims</h3>"
        "<table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>"
        "<tr><td style='padding:6px;background:#f8f9fa;'>Total received</td>"
        "<td style='padding:6px;'><strong>{total_received}</strong></td></tr>"
        "<tr><td style='padding:6px;background:#f8f9fa;'>Total resolved</td>"
        "<td style='padding:6px;'><strong>{total_resolved}</strong></td></tr>"
        "<tr><td style='padding:6px;background:#f8f9fa;'>Average resolution time</td>"
        "<td style='padding:6px;'><strong>{avg_resolution_time}</strong></td></tr>"
        "</table>"

        "<h4 style='color:#555;'>By criticality</h4>"
        "<table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>"
        "<tr style='background:#ecf0f1;'><th style='padding:6px;text-align:left;'>Level</th>"
        "<th style='padding:6px;text-align:right;'>Count</th><th style='padding:6px;text-align:right;'>%</th></tr>"
        "<tr style='border-left:4px solid #e74c3c;'>"
        "<td style='padding:6px;'>High</td>"
        "<td style='padding:6px;text-align:right;'>{high_count}</td>"
        "<td style='padding:6px;text-align:right;'>{high_pct}</td></tr>"
        "<tr style='border-left:4px solid #e67e22;'>"
        "<td style='padding:6px;'>Medium</td>"
        "<td style='padding:6px;text-align:right;'>{medium_count}</td>"
        "<td style='padding:6px;text-align:right;'>{medium_pct}</td></tr>"
        "<tr style='border-left:4px solid #27ae60;'>"
        "<td style='padding:6px;'>Low</td>"
        "<td style='padding:6px;text-align:right;'>{low_count}</td>"
        "<td style='padding:6px;text-align:right;'>{low_pct}</td></tr>"
        "</table>"

        "<h4 style='color:#555;'>By category</h4>"
        "<table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>"
        "<tr style='background:#ecf0f1;'><th style='padding:6px;text-align:left;'>Category</th>"
        "<th style='padding:6px;text-align:right;'>Count</th><th style='padding:6px;text-align:right;'>%</th></tr>"
        "<tr style='border-left:4px solid #7f8c8d;'>"
        "<td style='padding:6px;'>Housekeeping</td>"
        "<td style='padding:6px;text-align:right;'>{cat_housekeeping_count}</td>"
        "<td style='padding:6px;text-align:right;'>{cat_housekeeping_pct}</td></tr>"
        "<tr style='border-left:4px solid #7f8c8d;'>"
        "<td style='padding:6px;'>Maintenance</td>"
        "<td style='padding:6px;text-align:right;'>{cat_maintenance_count}</td>"
        "<td style='padding:6px;text-align:right;'>{cat_maintenance_pct}</td></tr>"
        "<tr style='border-left:4px solid #7f8c8d;'>"
        "<td style='padding:6px;'>Guest Relations</td>"
        "<td style='padding:6px;text-align:right;'>{cat_guestrel_count}</td>"
        "<td style='padding:6px;text-align:right;'>{cat_guestrel_pct}</td></tr>"
        "<tr style='border-left:4px solid #7f8c8d;'>"
        "<td style='padding:6px;'>Dining</td>"
        "<td style='padding:6px;text-align:right;'>{cat_dining_count}</td>"
        "<td style='padding:6px;text-align:right;'>{cat_dining_pct}</td></tr>"
        "<tr style='border-left:4px solid #7f8c8d;'>"
        "<td style='padding:6px;'>Unknown</td>"
        "<td style='padding:6px;text-align:right;'>{cat_unknown_count}</td>"
        "<td style='padding:6px;text-align:right;'>{cat_unknown_pct}</td></tr>"
        "</table>"

        "<h3 style='color:#2c3e50;'>Survey Scores</h3>"
        "<table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>"
        "<tr><td style='padding:6px;background:#f8f9fa;'>Room satisfaction</td>"
        "<td style='padding:6px;'><strong>{room_satisfaction_avg}</strong></td></tr>"
        "<tr><td style='padding:6px;background:#f8f9fa;'>Room reception</td>"
        "<td style='padding:6px;'><strong>{room_reception_avg}</strong></td></tr>"
        "<tr><td style='padding:6px;background:#f8f9fa;'>Restaurant experience</td>"
        "<td style='padding:6px;'><strong>{restaurant_avg}</strong></td></tr>"
        "</table>"

        "<h3 style='color:#2c3e50;'>Yesterday's Menu — Dish Scores</h3>"
        "<table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>"
        "<tr style='background:#ecf0f1;'><th style='padding:6px;text-align:left;'>Dish</th>"
        "<th style='padding:6px;text-align:right;'>Score</th></tr>"
        "{dishes_rows}"
        "</table>"

        "<p style='color:#7f8c8d;font-size:12px;margin-top:24px;'>— Bodor</p>"
        "</body></html>"
    ),
}

# ---- Helpers ----------------------------------------------------------------


def _score_or_dash(value) -> str:
    return f"{round(float(value), 2)}" if value is not None else "-"


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{round(count / total * 100)}%"


def _compute_yesterday_range(tz_name: str):
    """Return (yesterday_local_date, date_from_utc, date_to_utc) for the given timezone.

    'Yesterday' is the calendar day before today in the namespace's local time.
    date_from/date_to are naive UTC datetimes matching the local day boundaries,
    suitable for filtering DB timestamps stored as naive UTC.
    """
    tz = ZoneInfo(tz_name)
    local_now = datetime.now(tz)
    local_yesterday = (local_now - timedelta(days=1)).date()

    # Local midnight boundaries for yesterday, then convert to UTC and strip tzinfo
    local_start = datetime(local_yesterday.year, local_yesterday.month, local_yesterday.day,
                           0, 0, 0, tzinfo=tz)
    local_end = datetime(local_yesterday.year, local_yesterday.month, local_yesterday.day,
                         23, 59, 59, 999999, tzinfo=tz)

    date_from = local_start.astimezone(dt_timezone.utc).replace(tzinfo=None)
    date_to = local_end.astimezone(dt_timezone.utc).replace(tzinfo=None)

    return local_yesterday, date_from, date_to


def _get_claims_stats(db: Session, ns_id: int, date_from: datetime, date_to: datetime) -> dict:
    base = [
        Claim.namespace_id == ns_id,
        Claim.created_at >= date_from,
        Claim.created_at <= date_to,
    ]

    total_received = db.query(func.count(Claim.id)).filter(and_(*base)).scalar() or 0

    resolved_statuses = [
        ClaimStatus.resolved.value,
        ClaimStatus.closed.value,
        ClaimStatus.rejected.value,
    ]
    total_resolved = (
        db.query(func.count(Claim.id))
        .filter(and_(*base, Claim.status.in_(resolved_statuses)))
        .scalar() or 0
    )

    avg_min = (
        db.query(
            func.avg(extract("epoch", Claim.resolve_claim_time - Claim.created_at) / 60)
        )
        .filter(and_(*base, Claim.resolve_claim_time.isnot(None), Claim.status.in_(resolved_statuses)))
        .scalar()
    )

    criticality_rows = (
        db.query(Claim.criticality, func.count(Claim.id))
        .filter(and_(*base))
        .group_by(Claim.criticality)
        .all()
    )
    per_criticality = {r[0]: r[1] for r in criticality_rows}

    category_rows = (
        db.query(Claim.claim_category, func.count(Claim.id))
        .filter(and_(*base))
        .group_by(Claim.claim_category)
        .all()
    )
    per_category = {r[0]: r[1] for r in category_rows}

    return {
        "total_received": total_received,
        "total_resolved": total_resolved,
        "avg_resolution_min": avg_min,
        "per_criticality": per_criticality,
        "per_category": per_category,
    }


def _survey_avg(values) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _get_survey_averages(db: Session, ns_id: int, date_from: datetime, date_to: datetime) -> dict:
    room_row = (
        db.query(
            func.avg(DailyRoomSatisfactionSurvey.Q1),
            func.avg(DailyRoomSatisfactionSurvey.Q2),
            func.avg(DailyRoomSatisfactionSurvey.Q3),
            func.avg(DailyRoomSatisfactionSurvey.Q4),
        )
        .filter(
            DailyRoomSatisfactionSurvey.namespace_id == ns_id,
            DailyRoomSatisfactionSurvey.created_at >= date_from,
            DailyRoomSatisfactionSurvey.created_at <= date_to,
        )
        .one()
    )

    reception_row = (
        db.query(
            func.avg(RoomReceptionSurvey.Q1),
            func.avg(RoomReceptionSurvey.Q2),
            func.avg(RoomReceptionSurvey.Q3),
            func.avg(RoomReceptionSurvey.Q4),
        )
        .filter(
            RoomReceptionSurvey.namespace_id == ns_id,
            RoomReceptionSurvey.created_at >= date_from,
            RoomReceptionSurvey.created_at <= date_to,
        )
        .one()
    )

    restaurant_row = (
        db.query(
            func.avg(DailyRestaurantSurvey.Q1),
            func.avg(DailyRestaurantSurvey.Q2),
            func.avg(DailyRestaurantSurvey.Q3),
        )
        .filter(
            DailyRestaurantSurvey.namespace_id == ns_id,
            DailyRestaurantSurvey.created_at >= date_from,
            DailyRestaurantSurvey.created_at <= date_to,
        )
        .one()
    )

    return {
        "room_satisfaction_avg": _survey_avg(room_row),
        "room_reception_avg": _survey_avg(reception_row),
        "restaurant_avg": _survey_avg(restaurant_row),
    }


def _get_dish_scores(
    db: Session, ns_id: int, yesterday: date, date_from: datetime, date_to: datetime
) -> list[tuple[str, str]]:
    meal_ids = [
        r[0]
        for r in db.query(Meal.id)
        .filter(Meal.namespace_id == ns_id, Meal.meal_date == yesterday)
        .all()
    ]
    if not meal_ids:
        return []

    dish_ids = [
        r[0]
        for r in db.query(Menu.dishes_id)
        .filter(Menu.meal_id.in_(meal_ids))
        .distinct()
        .all()
    ]
    if not dish_ids:
        return []

    survey_rows = (
        db.query(DishesSurvey.dish_id, func.avg(DishesSurvey.Q))
        .filter(
            DishesSurvey.namespace_id == ns_id,
            DishesSurvey.dish_id.in_(dish_ids),
            DishesSurvey.created_at >= date_from,
            DishesSurvey.created_at <= date_to,
        )
        .group_by(DishesSurvey.dish_id)
        .all()
    )
    survey_map = {r[0]: r[1] for r in survey_rows}

    dishes = db.query(Dishes.id, Dishes.name).filter(Dishes.id.in_(dish_ids)).all()
    return [(d.name, _score_or_dash(survey_map.get(d.id))) for d in dishes]


def _build_dishes_rows_html(dish_scores: list[tuple[str, str]]) -> str:
    if not dish_scores:
        return "<tr><td colspan='2' style='padding:6px;color:#999;'>No dishes served yesterday</td></tr>"
    rows = []
    for name, score in dish_scores:
        rows.append(
            f"<tr><td style='padding:6px;'>{name}</td>"
            f"<td style='padding:6px;text-align:right;'>{score}</td></tr>"
        )
    return "".join(rows)


def _build_email_context(
    namespace_name: str,
    report_date: str,
    claims: dict,
    surveys: dict,
    dish_scores: list[tuple[str, str]],
) -> dict:
    total = claims["total_received"]
    per_crit = claims["per_criticality"]
    per_cat = claims["per_category"]

    high_n = per_crit.get("high", 0)
    medium_n = per_crit.get("medium", 0)
    low_n = per_crit.get("low", 0)

    avg_min = claims["avg_resolution_min"]
    if avg_min is not None:
        avg_str = f"{round(float(avg_min))} min"
    else:
        avg_str = "-"

    def cat_count(key):
        return per_cat.get(key, 0)

    dishes_rows = _build_dishes_rows_html(dish_scores)

    return {
        "namespace_name": namespace_name,
        "report_date": report_date,
        "total_received": str(total),
        "total_resolved": str(claims["total_resolved"]),
        "avg_resolution_time": avg_str,
        "high_count": str(high_n),
        "high_pct": _pct(high_n, total),
        "medium_count": str(medium_n),
        "medium_pct": _pct(medium_n, total),
        "low_count": str(low_n),
        "low_pct": _pct(low_n, total),
        "cat_housekeeping_count": str(cat_count(ClaimCategory.Housekeeping.value)),
        "cat_housekeeping_pct": _pct(cat_count(ClaimCategory.Housekeeping.value), total),
        "cat_maintenance_count": str(cat_count(ClaimCategory.Maintenance.value)),
        "cat_maintenance_pct": _pct(cat_count(ClaimCategory.Maintenance.value), total),
        "cat_guestrel_count": str(cat_count(ClaimCategory.Guest_Relations.value)),
        "cat_guestrel_pct": _pct(cat_count(ClaimCategory.Guest_Relations.value), total),
        "cat_dining_count": str(cat_count(ClaimCategory.Dining.value)),
        "cat_dining_pct": _pct(cat_count(ClaimCategory.Dining.value), total),
        "cat_unknown_count": str(cat_count(ClaimCategory.Unknown.value)),
        "cat_unknown_pct": _pct(cat_count(ClaimCategory.Unknown.value), total),
        "room_satisfaction_avg": _score_or_dash(surveys["room_satisfaction_avg"]),
        "room_reception_avg": _score_or_dash(surveys["room_reception_avg"]),
        "restaurant_avg": _score_or_dash(surveys["restaurant_avg"]),
        "dishes_rows": dishes_rows,
    }


def _format(template: str, context: dict) -> str:
    try:
        return template.format(**context)
    except (KeyError, ValueError) as e:
        logger.warning("Template formatting skipped: %s", e)
        return template


# ---- Handler ----------------------------------------------------------------


@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def send_daily_performance_report(
    namespace_id: int,
    job_id: str,
    payload: dict = None,
    **kwargs,
) -> dict:
    db_gen = get_db()
    db = next(db_gen)
    try:
        logger.info("[Job %s] Starting daily report for namespace %s", job_id, namespace_id)

        namespace = db.query(Namespace).filter(Namespace.id == namespace_id).first()
        if not namespace:
            raise ValueError(f"Namespace {namespace_id} not found")

        role_filters = [Users.role.contains([r]) for r in RECIPIENT_ROLES]
        recipients = (
            db.query(Users)
            .filter(Users.namespace_id == namespace_id, or_(*role_filters))
            .all()
        )
        if not recipients:
            logger.info("[Job %s] No recipients for namespace %s", job_id, namespace_id)
            return {"sent": 0, "namespace_id": namespace_id}

        yesterday, date_from, date_to = _compute_yesterday_range(namespace.timezone)
        report_date = yesterday.strftime("%Y-%m-%d")

        claims = _get_claims_stats(db, namespace_id, date_from, date_to)
        surveys = _get_survey_averages(db, namespace_id, date_from, date_to)
        dish_scores = _get_dish_scores(db, namespace_id, yesterday, date_from, date_to)

        namespace_name = namespace.hotel_name or f"Namespace {namespace_id}"
        context = _build_email_context(namespace_name, report_date, claims, surveys, dish_scores)

        # Pre-fill dishes_rows before translation so the LLM never sees raw HTML data rows
        template_for_translation = {
            k: v.replace("{dishes_rows}", context["dishes_rows"])
            if isinstance(v, str) and "{dishes_rows}" in v
            else v
            for k, v in EMAIL_TEMPLATE_EN.items()
        }

        by_lang: dict[str, list] = {}
        for r in recipients:
            lang = (r.pref_language or DEFAULT_LANGUAGE).lower()
            by_lang.setdefault(lang, []).append(r)

        sent = 0
        for lang, users in by_lang.items():
            logger.info("[Job %s] Sending to %s recipient(s) in %s", job_id, len(users), lang)
            try:
                tpl = _load_or_translate(
                    CachingCollectionName.DAILY_REPORT_EMAIL_TEMPLATES,
                    template_for_translation,
                    lang,
                )
            except Exception as e:
                logger.error("[Job %s] Translation failed for %s, using English: %s", job_id, lang, e)
                tpl = template_for_translation

            subject = _format(tpl["subject"], context)
            body_html = _format(tpl["body_html"], context)

            for user in users:
                if not user.user_email:
                    continue
                try:
                    _send_email(user.user_email, subject, body_html)
                    sent += 1
                except Exception as e:
                    logger.error("[Job %s] Email failed user=%s: %s", job_id, user.id, e)

        logger.info("[Job %s] Completed: sent %s email(s) for namespace %s", job_id, sent, namespace_id)
        return {"sent": sent, "namespace_id": namespace_id}

    finally:
        try:
            db.close()
        except Exception as e:
            logger.error("[Job %s] DB close error: %s", job_id, e)
