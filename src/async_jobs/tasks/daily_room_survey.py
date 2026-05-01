from src.app.db.orm import get_db
from src.app.db.models import Guest
from src.settings import client
from src.app.globals.notification import send_push_notification
from .utils import get_current_guest_for_given_namespace
from src.app.globals.admin_notifications import send_admin_failure_notification
from src.app.globals.enum import CachingCollectionName
from src.app.gcp import firestore_client
import logging
import backoff

logger = logging.getLogger(__name__)


def send_admin_failure_notification_for_job(details: dict):
    """Extract job details and send admin notification on final failure."""
    try:
        args = details.get("args", [])
        kwargs = details.get("kwargs", {})
        namespace_id = args[0] if len(args) > 0 else kwargs.get("namespace_id")
        job_id = args[1] if len(args) > 1 else kwargs.get("job_id", "unknown")
        exception = details.get("exception")

        # Get database session for context
        db_generator = get_db()
        db = next(db_generator)

        try:
            guests_count = 0
            try:
                guests_ids = get_current_guest_for_given_namespace(
                    namespace_id, check_meal_eligibility=False, db=db
                )
                guests_count = len(guests_ids) if guests_ids else 0
            except:
                pass

            send_admin_failure_notification(
                namespace_id=namespace_id,
                task_name=details["target"].__name__,
                error_message=str(exception),
                task_id=job_id,
                task_category="Survey",
                additional_context={
                    "survey_type": "daily_room",
                    "guests_count": guests_count,
                    "attempts": details.get("tries", 0),
                },
            )
        finally:
            try:
                db.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {str(close_error)}")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {str(e)}", exc_info=True)


def create_room_survey_notif_body(guest_name: str, language: str):
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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


def create_room_survey_notif_title(language: str):
    """
    Generate daily room survey notification title with Firestore caching.

    Checks Firestore cache first, generates with OpenAI if not cached, then stores result.
    Replaces @lru_cache with persistent Firestore caching.
    """
    # Check Firestore cache first
    cached_doc = firestore_client.find_document(
        collection_name=CachingCollectionName.DAILY_ROOM_SURVEY_NOTIF_TITLES,
        params={"language": language},
    )
    if cached_doc:
        return cached_doc.get("title")

    # Generate new notification title if not cached
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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
                    '"🛏️ How Was Your Room Today? 😊"'
                ),
            },
        ],
    )
    title = completion.choices[0].message.content

    # Cache the generated title
    firestore_client.create_document(
        collection_name=CachingCollectionName.DAILY_ROOM_SURVEY_NOTIF_TITLES,
        data={"language": language, "title": title},
    )
    return title


def send_guest_room_survey_notif(guest_id: str, db=None):
    """Send daily room satisfaction survey notification to a specific guest"""
    if db is None:
        raise ValueError("Database session must be provided")

    try:
        logger.info(f"Sending room survey notification to guest {guest_id}")

        guest = db.query(Guest).filter(Guest.phone_number == guest_id).first()

        if not guest:
            logger.warning(f"Guest {guest_id} not found, skipping notification")
            return

        if not guest.current_device_token:
            logger.warning(
                f"Guest {guest_id} has no device token, skipping notification"
            )
            return

        # Generate notification content with OpenAI
        try:
            notif_title = create_room_survey_notif_title(guest.pref_language)
            notif_body = create_room_survey_notif_body(
                guest.first_name, guest.pref_language
            )
        except Exception as e:
            logger.error(
                f"Failed to generate notification content for guest {guest_id}: {str(e)}"
            )
            # Use fallback generic message
            notif_title = "🛏️ How Was Your Room Today? 😊"
            notif_body = f"Hello {guest.first_name}, how was your room today? Let us know your satisfaction in the daily survey in the app."

        # Send push notification
        try:
            send_push_notification(guest.current_device_token, notif_title, notif_body)
            logger.info(
                f"Successfully sent room survey notification to guest {guest_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to send push notification to guest {guest_id}: {str(e)}"
            )
            raise

    except Exception as e:
        logger.error(
            f"Error sending room survey notification to guest {guest_id}: {str(e)}",
            exc_info=True,
        )
        raise


def process_namespace_room_surveys(namespace_id: int, task_id: str, db=None) -> dict:
    """
    Process room survey notifications for a specific namespace.

    This extracts the core logic for sending room satisfaction survey notifications
    to all active guests in a single namespace.

    Args:
        namespace_id: Namespace to process
        task_id: Job ID for logging
        db: Database session

    Returns:
        Dict with sent count and error counts
    """
    sent_count = 0
    guest_error_count = 0

    try:
        logger.info(
            f"[Job {task_id}] Processing room surveys for namespace {namespace_id}"
        )

        # Get current guests for this namespace
        guests_ids = get_current_guest_for_given_namespace(namespace_id, db=db)

        if not guests_ids:
            logger.info(
                f"[Job {task_id}] No active guests found for namespace {namespace_id}"
            )
            return {
                "sent": 0,
                "guest_errors": 0,
                "namespace_id": namespace_id,
            }

        logger.info(
            f"[Job {task_id}] Found {len(guests_ids)} active guests in namespace {namespace_id}"
        )

        # Send notification to each guest
        for guest_phone in guests_ids:
            try:
                # guest_phone is now a plain string (phone number)
                send_guest_room_survey_notif(guest_phone, db=db)
                sent_count += 1
                logger.info(
                    f"[Job {task_id}] Sent room survey to guest {guest_phone} in namespace {namespace_id}"
                )

            except Exception as e:
                logger.error(
                    f"[Job {task_id}] Failed to send notification to guest {guest_phone} "
                    f"in namespace {namespace_id}: {str(e)}"
                )
                guest_error_count += 1

        logger.info(
            f"[Job {task_id}] Completed namespace {namespace_id}: "
            f"{sent_count} sent, {guest_error_count} guest errors"
        )

        if sent_count == 0 and guest_error_count > 0:
            logger.warning(
                f"[Job {task_id}] All notification attempts failed for namespace {namespace_id}"
            )
            raise Exception(
                f"All notification attempts failed for namespace {namespace_id}"
            )
        return {
            "sent": sent_count,
            "guest_errors": guest_error_count,
            "namespace_id": namespace_id,
        }
    except Exception as e:
        logger.error(
            f"[Job {task_id}] Critical error processing namespace {namespace_id}: {str(e)}",
            exc_info=True,
        )
        raise


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][1] if len(details['args']) > 1 else 'unknown')} "
        f"(namespace {details['kwargs'].get('namespace_id', details['args'][0] if details['args'] else 'unknown')})"
    ),
    on_giveup=send_admin_failure_notification_for_job,
)
def send_notif_daily_room_satisf_for_namespace(
    namespace_id: int, job_id: str, payload: dict = None, **kwargs,
):
    """
    Send daily room satisfaction survey notifications for a specific namespace.

    This function is designed for per-namespace processing with Pub/Sub delivery guarantees.

    Args:
        namespace_id: ID of the namespace to process
        job_id: Job ID for logging

    Returns:
        Dict with send counts and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """
    task_id = job_id
    db_generator = get_db()
    db = next(db_generator)

    try:
        logger.info(
            f"[Job {task_id}] Processing daily room surveys for namespace {namespace_id}"
        )

        # Process this namespace
        result = process_namespace_room_surveys(namespace_id, task_id, db=db)

        logger.info(f"[Job {task_id}] Completed namespace {namespace_id}: {result}")
        return result

    except Exception as e:
        logger.error(
            f"[Job {task_id}] Error processing namespace {namespace_id}: {str(e)}",
            exc_info=True,
        )
        # Re-raise to trigger backoff retry
        raise
    finally:
        try:
            db.close()
        except Exception as close_error:
            logger.error(
                f"[Job {task_id}] Error closing database connection: {str(close_error)}"
            )
