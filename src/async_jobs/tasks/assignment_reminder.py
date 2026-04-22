import logging
import backoff
from sqlalchemy.orm import Session
from src.app.db.controller import get_db
from src.app.db.models.users import Users
from src.app.globals.enum import CachingCollectionName
from src.app.globals.schema_models import Role
from src.app.globals.notification import send_push_notification
from src.app.gcp import firestore_client
from src.settings import client

logger = logging.getLogger(__name__)


def _make_on_backoff_warning(kind: str):
    def handler(details):
        logger.warning(
            f"[assignment_reminder] Retry {details['tries']}/3 for {kind} "
            f"(language={details['args'][0] if details['args'] else 'unknown'}): "
            f"{details.get('exception')}"
        )
    return handler


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    on_backoff=_make_on_backoff_warning("title"),
)
def create_notif_assignment_title(language: str) -> str:
    cached_doc = firestore_client.find_document(
        collection_name=CachingCollectionName.ASSIGNMENTS_REMINDERS_NOTIF_TITLES,
        params={"language": language},
    )
    if cached_doc:
        return cached_doc.get("title")

    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates short push notification titles "
                    "for hotel staff in different languages. "
                    "The title should remind supervisors to schedule housekeepers for the next day."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification title in {language}. "
                    "Use this example as structure:\n"
                    '"Action Required: Schedule Housekeepers for Tomorrow"'
                ),
            },
        ],
    )
    title = completion.choices[0].message.content

    firestore_client.create_document(
        collection_name=CachingCollectionName.ASSIGNMENTS_REMINDERS_NOTIF_TITLES,
        data={"language": language, "title": title},
    )
    return title


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    on_backoff=_make_on_backoff_warning("body"),
)
def create_notif_assignment_body(language: str) -> str:
    cached_doc = firestore_client.find_document(
        collection_name=CachingCollectionName.ASSIGNMENTS_REMINDERS_NOTIF_BODY,
        params={"language": language},
    )
    if cached_doc:
        return cached_doc.get("body")

    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that creates short push notification bodies "
                    "for hotel housekeeping supervisors in different languages. "
                    "The message should remind the supervisor to assign housekeepers for the next day."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a notification body in {language}. "
                    "Use this example as structure:\n"
                    '"Please assign the housekeepers for tomorrow to ensure smooth operations."'
                ),
            },
        ],
    )
    body = completion.choices[0].message.content

    firestore_client.create_document(
        collection_name=CachingCollectionName.ASSIGNMENTS_REMINDERS_NOTIF_BODY,
        data={"language": language, "body": body},
    )
    return body


def send_assignment_reminder(db: Session, user_id: str):
    if db is None:
        raise ValueError("Database session must be provided")

    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        logger.warning(f"User {user_id} not found, skipping assignment reminder")
        raise Exception(f"User {user_id} not found")

    fullname = f"{user.first_name} {user.last_name}".strip()

    if not user.current_device_token:
        logger.warning(
            f"User '{fullname}' is not connected to any mobile device yet, skipping assignment reminder"
        )
        raise Exception(f"User '{fullname}' has no device token")

    language = user.pref_language or "english"
    title = create_notif_assignment_title(language)
    body = create_notif_assignment_body(language)

    try:
        send_push_notification(user.current_device_token, title, body)
        logger.info(f"Assignment reminder sent to user '{fullname}' (id={user_id})")
    except Exception as e:
        logger.error(
            f"Failed to send push notification to user '{fullname}' (id={user_id}): {str(e)}"
        )
        raise


def get_housekeeping_supervisors(namespace_id: int, db: Session) -> list[Users]:
    return (
        db.query(Users)
        .filter(
            Users.namespace_id == namespace_id,
            Users.role.contains([Role.housekeeping_supervisor.value]),
        )
        .all()
    )


def _on_backoff_namespace_warning(details):
    ns = (
        details["kwargs"].get("namespace_id")
        or (details["args"][0] if details["args"] else "unknown")
    )
    job = (
        details["kwargs"].get("job_id")
        or (details["args"][1] if len(details["args"]) > 1 else "unknown")
    )
    logger.warning(
        f"[assignment_reminder] Retry {details['tries']}/3 "
        f"for job {job} (namespace {ns}): {details.get('exception')}"
    )


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    jitter=backoff.full_jitter,
    on_backoff=_on_backoff_namespace_warning,
)
def send_notif_assignments_reminder_for_namespace(
    namespace_id: int, job_id: str, payload: dict = None, **kwargs,
) -> dict:
    """
    Send assignment reminder push notifications to all housekeeping
    supervisors within a given namespace.

    This function is designed for per-namespace processing and is
    decorated with exponential backoff (3 retries) to handle transient
    failures gracefully.

    Workflow:
        1. Open a database session.
        2. Retrieve all users with the housekeeping_supervisor role
           that belong to the given namespace.
        3. For each supervisor, generate a localised notification title
           and body (AI-generated, Firestore-cached) and dispatch a
           push notification to their registered device token.
        4. Track sent/error counts and raise if every attempt failed,
           so the backoff decorator can trigger a retry.

    Args:
        namespace_id: ID of the namespace whose supervisors should be
            notified.
        job_id: Unique identifier for this job execution, used in all
            log messages for traceability.

    Returns:
        A dict with the following keys:
            - sent (int): number of notifications successfully sent.
            - user_errors (int): number of per-user failures.
            - namespace_id (int): echo of the input namespace.

    Raises:
        Exception: Re-raised on critical failures so that the backoff
            decorator can schedule a retry.
    """
    db_generator = get_db()
    db = next(db_generator)

    try:
        logger.info(
            f"[Job {job_id}] Processing assignment reminders "
            f"for namespace {namespace_id}"
        )

        # Fetch all housekeeping supervisors for this namespace
        supervisors = get_housekeeping_supervisors(namespace_id, db)

        if not supervisors:
            logger.info(
                f"[Job {job_id}] No housekeeping supervisors found "
                f"for namespace {namespace_id}, skipping"
            )
            return {"sent": 0, "user_errors": 0, "namespace_id": namespace_id}

        logger.info(
            f"[Job {job_id}] Found {len(supervisors)} housekeeping "
            f"supervisor(s) in namespace {namespace_id}"
        )

        sent_count = 0
        user_error_count = 0

        # Notify each supervisor individually
        for supervisor in supervisors:
            try:
                send_assignment_reminder(db=db, user_id=supervisor.id)
                sent_count += 1
                logger.info(
                    f"[Job {job_id}] Sent assignment reminder to "
                    f"supervisor {supervisor.id} in namespace {namespace_id}"
                )
            except Exception as e:
                logger.error(
                    f"[Job {job_id}] Failed to notify supervisor "
                    f"{supervisor.id} in namespace {namespace_id}: {e}"
                )
                user_error_count += 1

        logger.info(
            f"[Job {job_id}] Completed namespace {namespace_id}: "
            f"{sent_count} sent, {user_error_count} error(s)"
        )

        # If every notification failed, raise so backoff retries the job
        if sent_count == 0 and user_error_count > 0:
            raise Exception(
                f"All notification attempts failed for namespace {namespace_id}"
            )

        return {
            "sent": sent_count,
            "user_errors": user_error_count,
            "namespace_id": namespace_id,
        }

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Critical error for namespace {namespace_id}: {e}",
            exc_info=True,
        )
        raise
    finally:
        # Always release the database connection
        try:
            db.close()
        except Exception as close_err:
            logger.error(
                f"[Job {job_id}] Error closing DB connection: {close_err}"
            )
