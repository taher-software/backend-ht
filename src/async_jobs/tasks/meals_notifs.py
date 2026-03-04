import backoff
import logging

from src.app.db.models import Guest
from src.app.db.orm import get_db
from src.app.globals.admin_notifications import send_admin_failure_notification
from src.app.globals.enum import MealEnum, CachingCollectionName
from src.app.globals.notification import send_push_notification
from src.app.gcp import firestore_client
from src.settings import client
from datetime import datetime
from sqlalchemy import and_
from src.app.db.models import Stay, Meal
from src.app.globals.utils import (
    breakfast_eligible_plans,
    lunch_eligible_plans,
    dinner_eligible_plans,
)

from .utils import get_concerned_namespaces

logger = logging.getLogger(__name__)


def send_meal_notification_failure_notification(details: dict):
    """
    Send admin notification when meal notification job fails after all retries.

    This is a backoff on_giveup handler that extracts job details and sends
    a failure notification to admins.

    Args:
        details: Backoff details dict containing args, kwargs, exception, tries, etc.
    """
    try:
        args = details.get("args", [])
        kwargs = details.get("kwargs", {})

        # Extract parameters (job_id is first arg, namespace_id is second)
        job_id = args[0] if len(args) > 0 else kwargs.get("job_id", "unknown")
        namespace_id = args[1] if len(args) > 1 else kwargs.get("namespace_id")
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
            task_category="Menu Notification",
            additional_context={
                "meal_type": meal_type,
                "attempts": details.get("tries", 0),
            },
        )
        logger.info(
            f"[Job {job_id}] Admin notification sent for {meal_type} menu failure in namespace {namespace_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to send admin failure notification: {str(e)}", exc_info=True
        )


def get_eligible_current_guest_for_given_meal_type(
    namespace_id: int, meal_type: MealEnum, db=None
):
    if db is None:
        raise ValueError("Database session must be provided")
    today = datetime.today().date()
    # Use eligible plans from globals/utils
    if meal_type == MealEnum.BREAKFAST:
        eligible_plans = breakfast_eligible_plans
    elif meal_type == MealEnum.LUNCH:
        eligible_plans = lunch_eligible_plans
    elif meal_type == MealEnum.DINNER:
        eligible_plans = dinner_eligible_plans
    else:
        return []
    guests_ids = (
        db.query(Stay.guest_id)
        .filter(
            and_(
                Stay.namespace_id == namespace_id,
                Stay.start_date <= today,
                Stay.end_date >= today,
                Stay.meal_plan.in_(eligible_plans),
            )
        )
        .all()
    )
    return [gid[0] for gid in guests_ids]


def meal_exists_today_for_namespace(namespace_id: int, meal_type: MealEnum, db) -> bool:
    today = datetime.today().date()
    return (
        db.query(Meal.id)
        .filter(
            and_(
                Meal.namespace_id == namespace_id,
                Meal.meal_type == meal_type,
                Meal.meal_date == today,
            )
        )
        .first()
        is not None
    )


def create_meal_notif_body(guest_name: str, meal_type: MealEnum, language: str):
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates short, friendly push notifications "
                    "for hotel guests in different languages. "
                    f"The notification should inform the guest that the {meal_type.value} menu is ready, "
                    "and invite them to check it in the app. Use emojis to make the message more welcoming."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification template in {language} for guest {guest_name}, "
                    f"Use this example as structure:\n"
                    f'"Hello {guest_name} 😊, your {meal_type.value} menu is ready! 🍽️ Tap the app to see what delicious options await you!"'
                ),
            },
        ],
    )
    return completion.choices[0].message.content


def create_meal_notif_title(language: str, meal_type: MealEnum):
    """
    Generate meal menu notification title with Firestore caching.

    Checks Firestore cache first, generates with OpenAI if not cached, then stores result.
    Replaces inline caching with persistent Firestore caching.

    Args:
        language: Target language for the notification title
        meal_type: Type of meal (BREAKFAST, LUNCH, DINNER)

    Returns:
        Localized notification title string
    """
    # Check Firestore cache first
    cached_doc = firestore_client.find_document(
        collection_name=CachingCollectionName.MEAL_MENU_NOTIF_TITLES,
        params={
            "language": language,
            "meal_type": meal_type.value,
        },
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
                    f"The title should be tailored to the guest using their preferred language and should reflect the {meal_type.value} menu."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification title in {language} for the {meal_type.value} menu. "
                    "Use this example as structure:\n"
                    f'"🍽️ Your {meal_type.value.capitalize()} Menu is Ready!"'
                ),
            },
        ],
    )
    title = completion.choices[0].message.content

    # Cache the generated title
    firestore_client.create_document(
        collection_name=CachingCollectionName.MEAL_MENU_NOTIF_TITLES,
        data={
            "language": language,
            "meal_type": meal_type.value,
            "title": title,
        },
    )
    return title


def send_guest_meal_notif(guest_id: int, meal_type: MealEnum, db=None):
    """Send meal menu notification to a specific guest"""
    if db is None:
        raise ValueError("Database session must be provided")

    try:
        logger.info(f"Sending {meal_type.value} menu notification to guest {guest_id}")

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
            notif_title = create_meal_notif_title(guest.pref_language, meal_type)
            notif_body = create_meal_notif_body(
                guest.first_name, meal_type, guest.pref_language
            )
        except Exception as e:
            logger.error(
                f"Failed to generate notification content for guest {guest_id}: {str(e)}"
            )
            # Use fallback generic message
            notif_title = f"🍽️ Your {meal_type.value.capitalize()} Menu is Ready!"
            notif_body = f"Hello {guest.first_name}, your {meal_type.value} menu is ready! Check the app to see what delicious options await you."

        # Send push notification
        try:
            send_push_notification(guest.current_device_token, notif_title, notif_body)
            logger.info(
                f"Successfully sent {meal_type.value} menu notification to guest {guest_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to send push notification to guest {guest_id}: {str(e)}"
            )
            raise

    except Exception as e:
        logger.error(
            f"Error sending {meal_type.value} menu notification to guest {guest_id}: {str(e)}",
            exc_info=True,
        )
        raise


# ============================================================================
# NAMESPACE-SPECIFIC TASKS (for manual triggering via API endpoints)
# ============================================================================


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][0] if details['args'] else 'unknown')} "
        f"(namespace {details['kwargs'].get('namespace_id', details['args'][1] if len(details['args']) > 1 else 'unknown')})"
    ),
    on_giveup=send_meal_notification_failure_notification,
)
def send_notif_breakfast_menu_for_namespace(job_id: str, namespace_id: int):
    """
    Send breakfast menu notifications to all eligible guests in a specific namespace.

    This job is designed for per-namespace processing with Pub/Sub delivery guarantees.

    Args:
        job_id: Unique identifier for this job execution
        namespace_id: The ID of the namespace to process

    Returns:
        dict: Statistics about sent notifications and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """
    db_generator = get_db()
    db = next(db_generator)

    sent_count = 0
    guest_error_count = 0

    try:
        logger.info(
            f"[Job {job_id}] Starting breakfast menu notification for namespace {namespace_id}"
        )

        if not meal_exists_today_for_namespace(namespace_id, MealEnum.BREAKFAST, db):
            logger.info(
                f"[Job {job_id}] No breakfast meal found today for namespace {namespace_id}, skipping"
            )
            return {"namespace_id": namespace_id, "sent": 0, "guest_errors": 0, "total_guests": 0}

        # Get eligible guests for this namespace
        try:
            guests_ids = get_eligible_current_guest_for_given_meal_type(
                namespace_id, MealEnum.BREAKFAST, db=db
            )
        except Exception as e:
            logger.error(
                f"[Job {job_id}] Failed to get guests for namespace {namespace_id}: {str(e)}",
                exc_info=True,
            )
            raise

        if not guests_ids:
            logger.info(
                f"[Job {job_id}] No eligible guests found for namespace {namespace_id}"
            )
            return {
                "namespace_id": namespace_id,
                "sent": 0,
                "guest_errors": 0,
                "total_guests": 0,
            }

        logger.info(
            f"[Job {job_id}] Found {len(guests_ids)} eligible guests in namespace {namespace_id}"
        )

        # Send notification to each guest
        for g_id in guests_ids:
            try:
                # g_id is typically a tuple (phone_number,) or just phone_number
                guest_phone = g_id[0] if isinstance(g_id, (tuple, list)) else g_id
                send_guest_meal_notif(guest_phone, MealEnum.BREAKFAST, db=db)
                sent_count += 1
            except Exception as e:
                logger.error(
                    f"[Job {job_id}] Failed to send notification to guest {g_id}: {str(e)}"
                )
                guest_error_count += 1
                continue

        if sent_count == 0 and guest_error_count > 0:
            logger.warning(
                f"[Job {job_id}] No notifications were sent for namespace {namespace_id}"
            )
            raise Exception(
                f"All notification attempts failed for namespace {namespace_id}"
            )

        logger.info(
            f"[Job {job_id}] Breakfast menu notification completed for namespace {namespace_id}: "
            f"{sent_count}/{len(guests_ids)} sent successfully"
        )
        return {
            "namespace_id": namespace_id,
            "sent": sent_count,
            "guest_errors": guest_error_count,
            "total_guests": len(guests_ids),
        }

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Error in breakfast menu notification "
            f"for namespace {namespace_id}: {str(e)}",
            exc_info=True,
        )
        # Re-raise to trigger backoff retry
        raise

    finally:
        try:
            db.close()
        except Exception as e:
            logger.error(f"[Job {job_id}] Error closing database connection: {str(e)}")


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][0] if details['args'] else 'unknown')} "
        f"(namespace {details['kwargs'].get('namespace_id', details['args'][1] if len(details['args']) > 1 else 'unknown')})"
    ),
    on_giveup=send_meal_notification_failure_notification,
)
def send_notif_lunch_menu_for_namespace(job_id: str, namespace_id: int):
    """
    Send lunch menu notifications to all eligible guests in a specific namespace.

    This job is designed for per-namespace processing with Pub/Sub delivery guarantees.

    Args:
        job_id: Unique identifier for this job execution
        namespace_id: The ID of the namespace to process

    Returns:
        dict: Statistics about sent notifications and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """
    db_generator = get_db()
    db = next(db_generator)

    sent_count = 0
    guest_error_count = 0

    try:
        logger.info(
            f"[Job {job_id}] Starting lunch menu notification for namespace {namespace_id}"
        )

        if not meal_exists_today_for_namespace(namespace_id, MealEnum.LUNCH, db):
            logger.info(
                f"[Job {job_id}] No lunch meal found today for namespace {namespace_id}, skipping"
            )
            return {"namespace_id": namespace_id, "sent": 0, "guest_errors": 0, "total_guests": 0}

        # Get eligible guests for this namespace
        try:
            guests_ids = get_eligible_current_guest_for_given_meal_type(
                namespace_id, MealEnum.LUNCH, db=db
            )
        except Exception as e:
            logger.error(
                f"[Job {job_id}] Failed to get guests for namespace {namespace_id}: {str(e)}",
                exc_info=True,
            )
            raise

        if not guests_ids:
            logger.info(
                f"[Job {job_id}] No eligible guests found for namespace {namespace_id}"
            )
            return {
                "namespace_id": namespace_id,
                "sent": 0,
                "guest_errors": 0,
                "total_guests": 0,
            }

        logger.info(
            f"[Job {job_id}] Found {len(guests_ids)} eligible guests in namespace {namespace_id}"
        )

        # Send notification to each guest
        for g_id in guests_ids:
            try:
                # g_id is typically a tuple (phone_number,) or just phone_number
                guest_phone = g_id[0] if isinstance(g_id, (tuple, list)) else g_id
                send_guest_meal_notif(guest_phone, MealEnum.LUNCH, db=db)
                sent_count += 1
            except Exception as e:
                logger.error(
                    f"[Job {job_id}] Failed to send notification to guest {g_id}: {str(e)}"
                )
                guest_error_count += 1

        if sent_count == 0 and guest_error_count > 0:
            logger.warning(
                f"[Job {job_id}] No notifications were sent for namespace {namespace_id}"
            )
            raise Exception(
                f"All notification attempts failed for namespace {namespace_id}"
            )

        logger.info(
            f"[Job {job_id}] Lunch menu notification completed for namespace {namespace_id}: "
            f"{sent_count}/{len(guests_ids)} sent successfully"
        )

        return {
            "namespace_id": namespace_id,
            "sent": sent_count,
            "guest_errors": guest_error_count,
            "total_guests": len(guests_ids),
        }

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Error in lunch menu notification "
            f"for namespace {namespace_id}: {str(e)}",
            exc_info=True,
        )
        # Re-raise to trigger backoff retry
        raise

    finally:
        try:
            db.close()
        except Exception as e:
            logger.error(f"[Job {job_id}] Error closing database connection: {str(e)}")


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    on_backoff=lambda details: logger.warning(
        f"Retry {details['tries']}/3 for job {details['kwargs'].get('job_id', details['args'][0] if details['args'] else 'unknown')} "
        f"(namespace {details['kwargs'].get('namespace_id', details['args'][1] if len(details['args']) > 1 else 'unknown')})"
    ),
    on_giveup=send_meal_notification_failure_notification,
)
def send_notif_dinner_menu_for_namespace(job_id: str, namespace_id: int):
    """
    Send dinner menu notifications to all eligible guests in a specific namespace.

    This job is designed for per-namespace processing with Pub/Sub delivery guarantees.

    Args:
        job_id: Unique identifier for this job execution
        namespace_id: The ID of the namespace to process

    Returns:
        dict: Statistics about sent notifications and errors

    Raises:
        Exception: On critical failures (triggers retry via backoff)
    """
    db_generator = get_db()
    db = next(db_generator)

    sent_count = 0
    guest_error_count = 0

    try:
        logger.info(
            f"[Job {job_id}] Starting dinner menu notification for namespace {namespace_id}"
        )

        if not meal_exists_today_for_namespace(namespace_id, MealEnum.DINNER, db):
            logger.info(
                f"[Job {job_id}] No dinner meal found today for namespace {namespace_id}, skipping"
            )
            return {"namespace_id": namespace_id, "sent": 0, "guest_errors": 0, "total_guests": 0}

        # Get eligible guests for this namespace
        try:
            guests_ids = get_eligible_current_guest_for_given_meal_type(
                namespace_id, MealEnum.DINNER, db=db
            )
        except Exception as e:
            logger.error(
                f"[Job {job_id}] Failed to get guests for namespace {namespace_id}: {str(e)}",
                exc_info=True,
            )
            raise

        if not guests_ids:
            logger.info(
                f"[Job {job_id}] No eligible guests found for namespace {namespace_id}"
            )
            return {
                "namespace_id": namespace_id,
                "sent": 0,
                "guest_errors": 0,
                "total_guests": 0,
            }

        logger.info(
            f"[Job {job_id}] Found {len(guests_ids)} eligible guests in namespace {namespace_id}"
        )

        # Send notification to each guest
        for g_id in guests_ids:
            try:
                # g_id is typically a tuple (phone_number,) or just phone_number
                guest_phone = g_id[0] if isinstance(g_id, (tuple, list)) else g_id
                send_guest_meal_notif(guest_phone, MealEnum.DINNER, db=db)
                sent_count += 1
            except Exception as e:
                logger.error(
                    f"[Job {job_id}] Failed to send notification to guest {g_id}: {str(e)}"
                )
                guest_error_count += 1
                continue

        if sent_count == 0 and guest_error_count > 0:
            logger.warning(
                f"[Job {job_id}] No notifications were sent for namespace {namespace_id}"
            )
            raise Exception(
                f"All notification attempts failed for namespace {namespace_id}"
            )

        logger.info(
            f"[Job {job_id}] Dinner menu notification completed for namespace {namespace_id}: "
            f"{sent_count}/{len(guests_ids)} sent successfully"
        )

        return {
            "namespace_id": namespace_id,
            "sent": sent_count,
            "guest_errors": guest_error_count,
            "total_guests": len(guests_ids),
        }

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Error in dinner menu notification "
            f"for namespace {namespace_id}: {str(e)}",
            exc_info=True,
        )
        # Re-raise to trigger backoff retry
        raise

    finally:
        try:
            db.close()
        except Exception as e:
            logger.error(f"[Job {job_id}] Error closing database connection: {str(e)}")
