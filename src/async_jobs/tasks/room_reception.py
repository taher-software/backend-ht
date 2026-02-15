from datetime import datetime, timedelta
from src.app.db.orm import get_db
from src.app.db.models import Namespace
from src.app.db.models import Stay
from src.app.db.models import Guest
from sqlalchemy import and_
from src.app.globals.notification import send_push_notification
from src.app.globals.admin_notifications import send_admin_failure_notification
from src.app.globals.enum import CachingCollectionName
from src.app.gcp import firestore_client
from src.settings import client
import backoff
import logging

logger = logging.getLogger(__name__)


def create_room_reception_survey_notif_title(language: str):
    """
    Generate room reception survey notification title with Firestore caching.

    Checks Firestore cache first, generates with OpenAI if not cached, then stores result.
    Replaces @lru_cache with persistent Firestore caching.

    Args:
        language: Target language for the notification title

    Returns:
        Localized notification title string
    """
    # Check Firestore cache first
    cached_doc = firestore_client.find_document(
        collection_name=CachingCollectionName.ROOM_RECEPTION_SURVEY_NOTIF_TITLES,
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
                    '"🛏️ Welcome! How Is Your Room?"'
                ),
            },
        ],
    )
    title = completion.choices[0].message.content

    # Cache the generated title
    firestore_client.create_document(
        collection_name=CachingCollectionName.ROOM_RECEPTION_SURVEY_NOTIF_TITLES,
        data={"language": language, "title": title},
    )
    return title


def create_room_reception_survey_notif_body(guest_name: str, language: str):
    """
    Generate room reception survey notification body in the specified language.

    Args:
        guest_name: Name of the guest to personalize the notification
        language: Target language for the notification body

    Returns:
        Localized notification body string
    """
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates short push notifications "
                    "for hotel guests in different languages. "
                    "The notification should ask the guest about their room and initial experience, "
                    "mention that the survey is inside the app."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification template in {language} for guest {guest_name}, "
                    "Use this example as structure:\n"
                    '"Hello {guest_name}, welcome to our hotel! How is your room? Please share your first impressions in the reception survey in the app."'
                ),
            },
        ],
    )
    return completion.choices[0].message.content


def send_guest_room_reception_survey_notif(guest_id: str, db=None):
    """Send room reception survey notification to a specific guest"""
    if db is None:
        raise ValueError("Database session must be provided")

    try:
        logger.info(f"Sending room reception survey notification to guest {guest_id}")

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
            notif_title = create_room_reception_survey_notif_title(guest.pref_language)
            notif_body = create_room_reception_survey_notif_body(
                guest.first_name, guest.pref_language
            )
        except Exception as e:
            logger.error(
                f"Failed to generate notification content for guest {guest_id}: {str(e)}"
            )
            # Use fallback generic message
            notif_title = "🛏️ Welcome! How Is Your Room?"
            notif_body = f"Hello {guest.first_name}, welcome to our hotel! How is your room? Please share your first impressions in the reception survey in the app."

        # Send push notification
        try:
            send_push_notification(guest.current_device_token, notif_title, notif_body)
            logger.info(
                f"Successfully sent room reception survey notification to guest {guest_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to send push notification to guest {guest_id}: {str(e)}"
            )
            raise

    except Exception as e:
        logger.error(
            f"Error sending room reception survey notification to guest {guest_id}: {str(e)}",
            exc_info=True,
        )
        raise


def send_admin_notification_on_final_failure(details: dict):
    """
    Send admin notification when a room reception survey job fails after all retries.

    This is a backoff on_giveup handler that extracts job details and sends
    a failure notification to admins. Works with guest-focused signature:
    send_notif_room_reception_satisf_for_guest(job_id, guest_id, namespace_id=None)

    Args:
        details: Backoff details dict containing args, kwargs, exception, tries, etc.
    """
    try:
        args = details.get("args", [])
        kwargs = details.get("kwargs", {})

        # Extract parameters based on new signature: (job_id, guest_id, namespace_id=None)
        job_id = args[0] if len(args) > 0 else kwargs.get("job_id", "unknown")
        guest_id = args[1] if len(args) > 1 else kwargs.get("guest_id", "unknown")
        namespace_id = args[2] if len(args) > 2 else kwargs.get("namespace_id")
        exception = details.get("exception")

        # Get database session for context
        db_generator = get_db()
        db = next(db_generator)

        try:
            # Get guest information for context
            guest_name = "Unknown"
            try:
                guest = db.query(Guest).filter(Guest.phone_number == guest_id).first()
                if guest:
                    guest_name = f"{guest.first_name} {guest.last_name}".strip()
            except:
                pass

            send_admin_failure_notification(
                namespace_id=namespace_id if namespace_id else 0,
                task_name=details["target"].__name__,
                error_message=str(exception),
                task_id=job_id,
                task_category="Survey",
                additional_context={
                    "survey_type": "room_reception_survey",
                    "attempts": details.get("tries", 0),
                    "guest_id": guest_id,
                    "guest_name": guest_name,
                    "affected_guests": 1,
                },
            )
            logger.info(
                f"[Job {job_id}] Admin notification sent for room reception survey failure for guest {guest_id}"
            )
        finally:
            try:
                db.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {str(close_error)}")

    except Exception as e:
        logger.error(f"Failed to send admin notification: {str(e)}", exc_info=True)


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    max_time=3600,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][0] if details['args'] else 'unknown')} "
        f"(guest {details['kwargs'].get('guest_id', 'unknown')})"
    ),
    on_giveup=send_admin_notification_on_final_failure,
)
def send_notif_room_reception_satisf_for_guest(
    job_id: str, guest_id: str, namespace_id: int = None
):
    """
    Send room reception survey notification to a specific guest.

    This job is designed for single-guest processing, triggered when a new stay is created.
    It sends a room reception survey notification to the guest after a configured delay.

    Args:
        job_id: Unique identifier for this job execution
        guest_id: Guest phone number for single-guest processing
        namespace_id: Optional ID of the namespace (for logging/context)

    Returns:
        Dict with send counts and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """
    db_generator = get_db()
    db = next(db_generator)

    try:
        logger.info(
            f"[Job {job_id}] Processing room reception survey for guest {guest_id}"
            + (f" in namespace {namespace_id}" if namespace_id else "")
        )

        send_guest_room_reception_survey_notif(guest_id, db=db)

        result = {
            "sent": 1,
            "guest_errors": 0,
            "guest_id": guest_id,
        }

        if namespace_id:
            result["namespace_id"] = namespace_id

        logger.info(f"[Job {job_id}] Completed for guest {guest_id}: {result}")
        return result

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Error processing guest {guest_id}: {str(e)}",
            exc_info=True,
        )
        # Re-raise to trigger backoff retry
        raise
    finally:
        try:
            db.close()
        except Exception as close_error:
            logger.error(
                f"[Job {job_id}] Error closing database connection: {str(close_error)}"
            )
