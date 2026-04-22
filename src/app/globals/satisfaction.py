import logging
from datetime import date

from src.app.gcp import pubsub_publisher
from src.app.globals.enum import JobType

logger = logging.getLogger(__name__)


def compute_survey_item_cote(check_in_date: date, check_out_date: date) -> float:
    num_days = max(1, (check_out_date - check_in_date).days)
    return 0.5 / ((8 * num_days) + 4)


def check_and_trigger_satisfaction_alert(
    old_score: float,
    new_score: float,
    threshold: float,
    namespace_id: int,
    stay_id: int,
    guest_id: str,
) -> None:
    if not (old_score >= threshold > new_score):
        return
    try:
        pubsub_publisher.publish_job(
            job_type=JobType.GUEST_SATISFACTION_ALERT,
            namespace_id=namespace_id,
            payload={"stay_id": stay_id, "guest_id": guest_id},
        )
        logger.info(
            f"Published GUEST_SATISFACTION_ALERT for stay={stay_id} "
            f"guest={guest_id} namespace={namespace_id} "
            f"(old={old_score:.4f}, new={new_score:.4f}, threshold={threshold})"
        )
    except Exception as e:
        logger.error(
            f"Failed to publish GUEST_SATISFACTION_ALERT for stay={stay_id}: {e}",
            exc_info=True,
        )
