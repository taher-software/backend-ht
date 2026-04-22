# ============================================================================
# PER-NAMESPACE MEAL REMINDER TASKS
#
# These tasks send reminders to dining managers to add meal menus.
# Retries are handled automatically by the backoff decorator.
# ============================================================================

import backoff
import logging

from sqlalchemy import or_
from src.app.db.controller import get_db
from src.app.db.models.namespace import Namespace
from src.app.db.models.users import Users
from src.app.globals.admin_notifications import send_admin_failure_notification
from src.app.globals.enum import MealEnum, CachingCollectionName
from src.app.globals.notification import send_push_notification
from src.app.globals.schema_models import Role
from src.settings import client
from src.app.gcp import firestore_client

logger = logging.getLogger(__name__)


def send_meal_reminder_failure_notification(details: dict):
    """
    Send admin notification when meal reminder job fails after all retries.

    This is a backoff on_giveup handler that extracts job details and sends
    a failure notification to admins.

    Args:
        details: Dictionary from backoff containing:
            - args: Positional arguments passed to the function
            - kwargs: Keyword arguments passed to the function
            - target: The function that failed
            - tries: Number of attempts made
            - exception: The exception that caused the failure
    """
    try:
        args = details.get("args", [])
        kwargs = details.get("kwargs", {})

        # Extract parameters (namespace_id, job_id)
        namespace_id = args[0] if len(args) > 0 else kwargs.get("namespace_id")
        job_id = args[1] if len(args) > 1 else kwargs.get("job_id", "unknown")
        exception = details.get("exception")

        # Determine meal type from function name
        func_name = details["target"].__name__
        if "breakfast" in func_name:
            meal_type = "breakfast"
        elif "lunch" in func_name:
            meal_type = "lunch"
        elif "dinner" in func_name:
            meal_type = "dinner"
        else:
            meal_type = "unknown"

        send_admin_failure_notification(
            namespace_id=namespace_id,
            task_name=func_name,
            error_message=str(exception),
            task_id=job_id,
            task_category="Meal Reminder",
            additional_context={
                "meal_type": meal_type,
                "attempts": details.get("tries", 0),
            },
        )
        logger.info(
            f"[Job {job_id}] Sent admin failure notification for {meal_type} reminder"
        )

    except Exception as e:
        logger.error(
            f"Failed to send admin failure notification: {str(e)}", exc_info=True
        )


def create_reminder_notif_title(
    language: str, meal_type: MealEnum, menu_time: str
) -> str:
    """
    Generate meal reminder notification title with Firestore caching.

    Checks Firestore cache first, generates with OpenAI if not cached, then stores result.
    Replaces @lru_cache with persistent Firestore caching.
    """
    # Check Firestore cache first
    cached_doc = firestore_client.find_document(
        collection_name=CachingCollectionName.MEAL_REMINDERS_NOTIF_TITLES,
        params={
            "language": language,
            "meal_type": meal_type.value,
            "menu_time": menu_time,
        },
    )
    if cached_doc:
        return cached_doc.get("title")
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates notification titles "
                    "for hotel staff in different languages. "
                    f"The title should remind the receiver to add the {meal_type.value} menu before {menu_time}. "
                    "Make it clear, urgent, and friendly. Use emojis if appropriate."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification title in {language} for the {meal_type.value} menu. "
                    f"Use this example as structure:\n"
                    f'"⏰ Please Add the {meal_type.value.capitalize()} Menu Before {menu_time}! 🍽️"'
                ),
            },
        ],
    )
    title = completion.choices[0].message.content
    # Cache the generated title
    firestore_client.create_document(
        collection_name=CachingCollectionName.MEAL_REMINDERS_NOTIF_TITLES,
        data={
            "language": language,
            "meal_type": meal_type.value,
            "menu_time": menu_time,
            "title": title,
        },
    )
    return title


def create_reminder_notif_body(
    user_name: str, language: str, meal_type: MealEnum, menu_time: str
) -> str:
    """
    Generate meal reminder notification body with Firestore caching.

    Checks Firestore cache first, generates with OpenAI if not cached, then stores result.
    Replaces @lru_cache with persistent Firestore caching.
    Note: user_name is included in cache key for personalization.
    """

    # Generate new notification body if not cached
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates friendly reminders "
                    "for hotel staff in different languages. "
                    f"The reminder should inform the staff member to add the {meal_type.value} menu before {menu_time}."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a reminder message in {language} for {user_name}, "
                    f"Use this example as structure:\n"
                    f'"Hello {user_name}, please remember to add the {meal_type.value} menu before {menu_time}. Thank you! 🙏"'
                ),
            },
        ],
    )
    body = completion.choices[0].message.content

    return body


def get_menu_time(namespace_id: int, meal_type: MealEnum, db=None) -> str | None:
    namespace = db.query(Namespace).filter(Namespace.id == namespace_id).first()
    if not namespace or not namespace.settings:
        return "Unknown time"
    menu_time_fields = {
        MealEnum.BREAKFAST: "breakfast_menu_time",  # Example: "8:00 AM"
        MealEnum.LUNCH: "lunch_menu_time",  # Example: "12:00 PM"
        MealEnum.DINNER: "dinner_menu_time",  # Example: "7:00 PM"
    }
    st = namespace.settings
    menu_time = getattr(st, menu_time_fields.get(meal_type), None)
    if not menu_time:
        return None
    return menu_time.strftime("%I:%M %p")  # Format as "HH:


def send_menu_reminder_notif(
    user_id: str, meal_type: MealEnum, menu_time: str, db=None
):
    """Send menu reminder notification to a specific user"""
    if db is None:
        raise ValueError("Database session is required")
    try:
        logger.info(f"Sending {meal_type.value} reminder to user {user_id}")

        user = db.query(Users).filter(Users.id == user_id).first()

        if not user:
            logger.warning(f"User {user_id} not found, skipping notification")
            return

        if not user.current_device_token:
            logger.warning(f"User {user_id} has no device token, skipping notification")
            return

        # Generate notification content with OpenAI
        try:
            notif_title = create_reminder_notif_title(
                user.pref_language, meal_type, menu_time
            )
            notif_body = create_reminder_notif_body(
                user.first_name, user.pref_language, meal_type, menu_time
            )
        except Exception as e:
            logger.error(
                f"Failed to generate notification content for user {user_id}: {str(e)}"
            )
            # Use fallback generic message
            notif_title = f"⏰ Please Add the {meal_type.value.capitalize()} Menu Before {menu_time}!"
            notif_body = f"Hello {user.first_name}, please remember to add the {meal_type.value} menu before {menu_time}. Thank you!"

        # Send push notification
        try:
            send_push_notification(user.current_device_token, notif_title, notif_body)
            logger.info(
                f"Successfully sent {meal_type.value} reminder to user {user_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to send push notification to user {user_id}: {str(e)}"
            )
            raise

    except Exception as e:
        logger.error(
            f"Error sending menu reminder to user {user_id}: {str(e)}", exc_info=True
        )
        raise


def get_dining_managers(namespace_id, db):
    allowed_roles = [
        Role.dining_supervisor.value,
    ]
    # Use OR with contains() for each role to check if array contains any allowed role
    users = (
        db.query(Users)
        .filter(Users.namespace_id == namespace_id)
        .filter(or_(*[Users.role.contains([role]) for role in allowed_roles]))
        .all()
    )
    return users


def process_namespace_meal_reminders(
    namespace_id: int, meal_type: MealEnum, menu_time: str, job_id: str, db=None
) -> dict:
    """
    Process meal reminders for a specific namespace.

    This extracts the core logic for sending reminders to dining managers
    in a single namespace.

    Args:
        namespace_id: Namespace to process
        meal_type: Type of meal (BREAKFAST, LUNCH, DINNER)
        menu_time: Formatted menu time string
        job_id: Job ID for logging

    Returns:
        Dict with sent count and error counts
    """

    sent_count = 0
    user_error_count = 0

    try:
        logger.info(
            f"[Job {job_id}] Processing {meal_type.value} reminders for namespace {namespace_id}"
        )

        # Get dining managers for this namespace
        users = get_dining_managers(namespace_id, db)

        if not users:
            logger.info(
                f"[Job {job_id}] No dining managers found for namespace {namespace_id}"
            )
            return {
                "sent": 0,
                "user_errors": 0,
                "namespace_id": namespace_id,
                "meal_type": meal_type.value,
            }

        logger.info(
            f"[Job {job_id}] Found {len(users)} dining managers in namespace {namespace_id}"
        )

        # Send reminders to each manager
        for user in users:
            try:
                send_menu_reminder_notif(user.id, meal_type, menu_time, db=db)
                sent_count += 1
                logger.info(
                    f"[Job {job_id}] Sent {meal_type.value} reminder to user {user.id} in namespace {namespace_id}"
                )

            except Exception as e:
                logger.error(
                    f"[Job {job_id}] Failed to send reminder to user {user.id} "
                    f"in namespace {namespace_id}: {str(e)}"
                )
                user_error_count += 1

        logger.info(
            f"[Job {job_id}] Completed namespace {namespace_id}: "
            f"{sent_count} sent, {user_error_count} user errors"
        )

        if sent_count == 0 and user_error_count > 0:
            logger.warning(
                f"[Job {job_id}] All notification attempts failed for namespace {namespace_id}"
            )
            raise Exception(
                f"All notification attempts failed for namespace {namespace_id}"
            )

        return {
            "sent": sent_count,
            "user_errors": user_error_count,
            "namespace_id": namespace_id,
            "meal_type": meal_type.value,
        }
    except Exception as e:
        logger.error(
            f"[Job {job_id}] Critical error processing namespace {namespace_id}: {str(e)}",
            exc_info=True,
        )
        raise


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    jitter=backoff.full_jitter,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][1] if len(details['args']) > 1 else 'unknown')} "
        f"(namespace {details['kwargs'].get('namespace_id', details['args'][0] if details['args'] else 'unknown')})"
    ),
    on_giveup=send_meal_reminder_failure_notification,
)
def send_notif_breakfast_menu_reminder_for_namespace(
    namespace_id: int, job_id: str, payload: dict = None, **kwargs,
):
    """
    Send breakfast menu reminders to dining managers of a specific namespace.

    This job is designed for per-namespace processing with Pub/Sub delivery guarantees.

    Args:
        namespace_id: ID of the namespace to process
        job_id: Unique job identifier for tracking

    Returns:
        Dict with send counts and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """

    meal_type = MealEnum.BREAKFAST
    db_generator = get_db()
    db = next(db_generator)

    try:
        logger.info(
            f"[Job {job_id}] Processing breakfast menu reminders for namespace {namespace_id}"
        )

        # Get menu time for this namespace
        try:
            menu_time = get_menu_time(namespace_id, meal_type, db=db)
            if menu_time is None:
                logger.warning(
                    f"[Job {job_id}] No breakfast menu time set for namespace {namespace_id}, skipping"
                )
                return {
                    "sent": 0,
                    "user_errors": 0,
                    "namespace_id": namespace_id,
                    "meal_type": meal_type.value,
                    "reason": "no_menu_time",
                }
        except Exception as e:
            logger.error(
                f"[Job {job_id}] Failed to get menu time for namespace {namespace_id}: {str(e)}"
            )
            raise

        # Process this namespace
        result = process_namespace_meal_reminders(
            namespace_id, meal_type, menu_time, job_id, db=db
        )

        logger.info(f"[Job {job_id}] Completed namespace {namespace_id}: {result}")
        return result

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Error processing namespace {namespace_id}: {str(e)}",
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


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    jitter=backoff.full_jitter,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][1] if len(details['args']) > 1 else 'unknown')} "
        f"(namespace {details['kwargs'].get('namespace_id', details['args'][0] if details['args'] else 'unknown')})"
    ),
    on_giveup=send_meal_reminder_failure_notification,
)
def send_notif_lunch_menu_reminder_for_namespace(
    namespace_id: int, job_id: str, payload: dict = None, **kwargs,
):
    """
    Send lunch menu reminders to dining managers of a specific namespace.

    This job is designed for per-namespace processing with Pub/Sub delivery guarantees.

    Args:
        namespace_id: ID of the namespace to process
        job_id: Unique job identifier for tracking

    Returns:
        Dict with send counts and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """

    meal_type = MealEnum.LUNCH
    db_generator = get_db()
    db = next(db_generator)

    try:
        logger.info(
            f"[Job {job_id}] Processing lunch menu reminders for namespace {namespace_id}"
        )

        # Get menu time for this namespace
        try:
            menu_time = get_menu_time(namespace_id, meal_type, db=db)
            if menu_time is None:
                logger.warning(
                    f"[Job {job_id}] No lunch menu time set for namespace {namespace_id}, skipping"
                )
                return {
                    "sent": 0,
                    "user_errors": 0,
                    "namespace_id": namespace_id,
                    "meal_type": meal_type.value,
                    "reason": "no_menu_time",
                }
        except Exception as e:
            logger.error(
                f"[Job {job_id}] Failed to get menu time for namespace {namespace_id}: {str(e)}"
            )
            raise

        # Process this namespace
        result = process_namespace_meal_reminders(
            namespace_id, meal_type, menu_time, job_id, db=db
        )

        logger.info(f"[Job {job_id}] Completed namespace {namespace_id}: {result}")
        return result

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Error processing namespace {namespace_id}: {str(e)}",
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


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    jitter=backoff.full_jitter,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][1] if len(details['args']) > 1 else 'unknown')} "
        f"(namespace {details['kwargs'].get('namespace_id', details['args'][0] if details['args'] else 'unknown')})"
    ),
    on_giveup=send_meal_reminder_failure_notification,
)
def send_notif_dinner_menu_reminder_for_namespace(
    namespace_id: int, job_id: str, payload: dict = None, **kwargs,
):
    """
    Send dinner menu reminders to dining managers of a specific namespace.

    This job is designed for per-namespace processing with Pub/Sub delivery guarantees.

    Args:
        namespace_id: ID of the namespace to process
        job_id: Unique job identifier for tracking

    Returns:
        Dict with send counts and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """

    meal_type = MealEnum.DINNER
    db_generator = get_db()
    db = next(db_generator)

    try:
        logger.info(
            f"[Job {job_id}] Processing dinner menu reminders for namespace {namespace_id}"
        )

        # Get menu time for this namespace
        try:
            menu_time = get_menu_time(namespace_id, meal_type, db=db)

            if menu_time is None:
                logger.warning(
                    f"[Job {job_id}] No dinner menu time set for namespace {namespace_id}, skipping"
                )
                return {
                    "sent": 0,
                    "user_errors": 0,
                    "namespace_id": namespace_id,
                    "meal_type": meal_type.value,
                    "reason": "no_menu_time",
                }
        except Exception as e:
            logger.error(
                f"[Job {job_id}] Failed to get menu time for namespace {namespace_id}: {str(e)}"
            )
            raise

        # Process this namespace
        result = process_namespace_meal_reminders(
            namespace_id, meal_type, menu_time, job_id, db=db
        )

        logger.info(f"[Job {job_id}] Completed namespace {namespace_id}: {result}")
        return result

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Error processing namespace {namespace_id}: {str(e)}",
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
