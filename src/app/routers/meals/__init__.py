from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from src.app.db.orm import get_db
from src.app.globals.authentication import CurrentUserIdentifier
from .modelsIn import MealCreateIn
from . import services
from src.app.globals.schema_models import Role
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from .modelsOut import MenuReminderBatchResponse, QueuedTask, FailedNamespace
import logging
from src.app.gcp import pubsub_publisher
from src.app.globals.enum import JobType, MealEnum
from src.app.globals.admin_notifications import send_batch_failure_summary
from fastapi import status
from .services import get_late_namespaces

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meals", tags=["meals"], responses={**validation_response})


@router.post("/", response_model=ApiResponse)
def create_meal(
    payload: MealCreateIn = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("user")),
):
    allowed_roles = {
        Role.owner.value,
        Role.admin.value,
        Role.supervisor.value,
        Role.dining_supervisor.value,
    }
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=403, detail="You do not have permission to create meals."
        )

    services.create_meal_with_menu(payload, current_user, db)

    return ApiResponse(data="Meal created successfully.")


@router.post("/send-breakfast-reminder", response_model=MenuReminderBatchResponse)
def send_breakfast_reminder(db: Session = Depends(get_db)):
    """
    Publish breakfast menu reminder Pub/Sub jobs for all late namespaces.

    This endpoint:
    1. Retrieves namespaces that haven't submitted breakfast menus
    2. Publishes a separate job for each namespace
    3. Handles errors and notifies admins on critical failures

    Returns:
        Batch response with published job IDs and namespace info
    """
    try:
        # Step 1: Get namespaces that need breakfast reminders
        logger.info("Retrieving namespaces for breakfast menu reminders")

        namespaces_ids = get_late_namespaces(
            meal_time_field="breakfast_menu_time", meal_type=MealEnum.BREAKFAST, db=db
        )

        if not namespaces_ids:
            logger.info("No namespaces need breakfast menu reminders")
            return MenuReminderBatchResponse(
                message="No namespaces require breakfast menu reminders",
                total_namespaces=0,
                queued_tasks=[],
                failed_namespaces=[],
            )

        logger.info(
            f"Found {len(namespaces_ids)} namespaces requiring breakfast reminders"
        )

        # Step 2: Publish a job for each namespace
        queued_tasks = []
        failed_namespaces = []

        for ns_id in namespaces_ids:
            try:
                # Publish job for this namespace
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.BREAKFAST_REMINDER, namespace_id=ns_id
                )

                queued_tasks.append(
                    QueuedTask(namespace_id=ns_id, task_id=job_id, status="queued")
                )

                logger.info(
                    f"Published breakfast reminder job for namespace {ns_id}: {job_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to publish job for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )

                failed_namespaces.append(
                    FailedNamespace(namespace_id=ns_id, error=str(e))
                )

        # Step 3: Send batch failure summary if there were failures
        if failed_namespaces:
            try:
                send_batch_failure_summary(
                    failed_namespaces=[
                        {"namespace_id": f.namespace_id, "error": f.error}
                        for f in failed_namespaces
                    ],
                    task_category="Meal Reminder",
                    total_attempted=len(namespaces_ids),
                    operation_name="Breakfast Reminder Queueing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary: {str(email_error)}"
                )

        # Step 4: Return batch response
        return MenuReminderBatchResponse(
            message=f"Published {len(queued_tasks)} breakfast reminder jobs",
            total_namespaces=len(namespaces_ids),
            queued_tasks=queued_tasks,
            failed_namespaces=failed_namespaces,
        )

    except Exception as e:
        logger.error(
            f"Critical error in send_breakfast_reminder endpoint: {str(e)}",
            exc_info=True,
        )

        # Return error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish breakfast reminder jobs: {str(e)}",
        )


@router.post("/send-lunch-reminder", response_model=MenuReminderBatchResponse)
def send_lunch_reminder(db: Session = Depends(get_db)):
    """
    Publish lunch menu reminder Pub/Sub jobs for all late namespaces.

    This endpoint:
    1. Retrieves namespaces that haven't submitted lunch menus
    2. Publishes a separate job for each namespace
    3. Handles errors and notifies admins on critical failures

    Returns:
        Batch response with published job IDs and namespace info
    """
    try:
        # Step 1: Get namespaces that need lunch reminders
        logger.info("Retrieving namespaces for lunch menu reminders")

        namespaces_ids = get_late_namespaces(
            meal_time_field="lunch_menu_time", meal_type=MealEnum.LUNCH, db=db
        )

        if not namespaces_ids:
            logger.info("No namespaces need lunch menu reminders")
            return MenuReminderBatchResponse(
                message="No namespaces require lunch menu reminders",
                total_namespaces=0,
                queued_tasks=[],
                failed_namespaces=[],
            )

        logger.info(f"Found {len(namespaces_ids)} namespaces requiring lunch reminders")

        # Step 2: Publish a job for each namespace
        queued_tasks = []
        failed_namespaces = []

        for ns_id in namespaces_ids:
            try:
                # Publish job for this namespace
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.LUNCH_REMINDER, namespace_id=ns_id
                )

                queued_tasks.append(
                    QueuedTask(namespace_id=ns_id, task_id=job_id, status="queued")
                )

                logger.info(
                    f"Published lunch reminder job for namespace {ns_id}: {job_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to publish job for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )

                failed_namespaces.append(
                    FailedNamespace(namespace_id=ns_id, error=str(e))
                )

        # Step 3: Send batch failure summary if there were failures
        if failed_namespaces:
            try:
                send_batch_failure_summary(
                    failed_namespaces=[
                        {"namespace_id": f.namespace_id, "error": f.error}
                        for f in failed_namespaces
                    ],
                    task_category="Meal Reminder",
                    total_attempted=len(namespaces_ids),
                    operation_name="Lunch Reminder Queueing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary: {str(email_error)}"
                )

        # Step 4: Return batch response
        return MenuReminderBatchResponse(
            message=f"Published {len(queued_tasks)} lunch reminder jobs",
            total_namespaces=len(namespaces_ids),
            queued_tasks=queued_tasks,
            failed_namespaces=failed_namespaces,
        )

    except Exception as e:
        logger.error(
            f"Critical error in send_lunch_reminder endpoint: {str(e)}", exc_info=True
        )

        # Return error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish lunch reminder jobs: {str(e)}",
        )


@router.post("/send-dinner-reminder", response_model=MenuReminderBatchResponse)
def send_dinner_reminder(db: Session = Depends(get_db)):
    """
    Publish dinner menu reminder Pub/Sub jobs for all late namespaces.

    This endpoint:
    1. Retrieves namespaces that haven't submitted dinner menus
    2. Publishes a separate job for each namespace
    3. Handles errors and notifies admins on critical failures

    Returns:
        Batch response with published job IDs and namespace info
    """
    try:
        # Step 1: Get namespaces that need dinner reminders
        logger.info("Retrieving namespaces for dinner menu reminders")

        namespaces_ids = get_late_namespaces(
            meal_time_field="dinner_menu_time", meal_type=MealEnum.DINNER, db=db
        )

        if not namespaces_ids:
            logger.info("No namespaces need dinner menu reminders")
            return MenuReminderBatchResponse(
                message="No namespaces require dinner menu reminders",
                total_namespaces=0,
                queued_tasks=[],
                failed_namespaces=[],
            )

        logger.info(
            f"Found {len(namespaces_ids)} namespaces requiring dinner reminders"
        )

        # Step 2: Publish a job for each namespace
        queued_tasks = []
        failed_namespaces = []

        for ns_id in namespaces_ids:
            try:
                # Publish job for this namespace
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.DINNER_REMINDER, namespace_id=ns_id
                )

                queued_tasks.append(
                    QueuedTask(namespace_id=ns_id, task_id=job_id, status="queued")
                )

                logger.info(
                    f"Published dinner reminder job for namespace {ns_id}: {job_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to publish job for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )

                failed_namespaces.append(
                    FailedNamespace(namespace_id=ns_id, error=str(e))
                )

        # Step 3: Send batch failure summary if there were failures
        if failed_namespaces:
            try:
                send_batch_failure_summary(
                    failed_namespaces=[
                        {"namespace_id": f.namespace_id, "error": f.error}
                        for f in failed_namespaces
                    ],
                    task_category="Meal Reminder",
                    total_attempted=len(namespaces_ids),
                    operation_name="Dinner Reminder Queueing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary: {str(email_error)}"
                )

        # Step 4: Return batch response
        return MenuReminderBatchResponse(
            message=f"Published {len(queued_tasks)} dinner reminder jobs",
            total_namespaces=len(namespaces_ids),
            queued_tasks=queued_tasks,
            failed_namespaces=failed_namespaces,
        )

    except Exception as e:
        logger.error(
            f"Critical error in send_dinner_reminder endpoint: {str(e)}", exc_info=True
        )

        # Return error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish dinner reminder jobs: {str(e)}",
        )
