import logging
from zoneinfo import ZoneInfo
from datetime import datetime

from sqlalchemy.orm import Session

from src.app.db.models import Namespace
from src.app.gcp import pubsub_publisher
from src.app.globals.enum import JobType

logger = logging.getLogger(__name__)


def get_namespaces_in_report_window(db: Session) -> list[tuple[int, str]]:
    """Return (namespace_id, local_date_str) for namespaces whose local time is 09:00–09:59."""
    namespaces = db.query(Namespace).all()
    result = []
    for ns in namespaces:
        if not ns.settings or not ns.timezone:
            continue
        try:
            tz = ZoneInfo(ns.timezone)
            local_now = datetime.now(tz)
            minutes_since_9am = local_now.hour * 60 + local_now.minute - 9 * 60
            if 0 <= minutes_since_9am < 60:
                local_date = local_now.date().isoformat()
                result.append((ns.id, local_date))
        except Exception as e:
            logger.error("Skipping namespace %s due to timezone error: %s", ns.id, e)
    return result


def publish_report_jobs(namespaces: list[tuple[int, str]]) -> int:
    """Publish one DAILY_PERFORMANCE_REPORT Pub/Sub job per namespace with a deterministic job_id.

    The job_id combines namespace_id and local report date so the worker's Firestore
    deduplication rejects duplicate scheduler invocations for the same namespace and day.
    """
    published = 0
    for ns_id, local_date in namespaces:
        job_id = f"daily-report-{ns_id}-{local_date}"
        try:
            pubsub_publisher.publish_job(
                job_type=JobType.DAILY_PERFORMANCE_REPORT,
                namespace_id=ns_id,
                job_id=job_id,
            )
            published += 1
            logger.info("Published daily report job %s for namespace %s", job_id, ns_id)
        except Exception as e:
            logger.error("Failed to publish daily report job for namespace %s: %s", ns_id, e)
    return published
