from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.app.db.orm import get_db
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.enum import MealEnum, JobType
from src.app.globals.admin_notifications import send_batch_failure_summary
from .services import (
    get_current_menu,
)
from .modelsOut import (
    CurrentMenuResponse,
    DishOut,
    TriggerNotificationResponse,
)

from src.app.gcp import pubsub_publisher
from src.async_jobs.tasks.utils import get_concerned_namespaces
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/get_current_menu", response_model=CurrentMenuResponse)
def get_current_menu_endpoint(
    db=Depends(get_db),
    current_guest: dict = Depends(CurrentUserIdentifier("guest")),
):
    """Get current menu for the guest based on time and eligibility"""
    dishes = get_current_menu(db, current_guest)

    return CurrentMenuResponse(
        dishes=[DishOut(**dish) for dish in dishes["menu"]],
        meal=dishes["meal_type"],
        meal_time_range=dishes["meal_time_range"],
    )


@router.post(
    "/trigger_breakfast_notifications", response_model=TriggerNotificationResponse
)
def trigger_breakfast_notifications(db=Depends(get_db)):
    """
    Trigger breakfast menu notifications for all eligible namespaces.

    This endpoint queries all namespaces where it's currently breakfast menu time
    and publishes a Pub/Sub job for each namespace to send notifications to eligible guests.

    Returns:
        TriggerNotificationResponse with statistics about published jobs
    """
    logger.info("Breakfast notification trigger endpoint called")

    job_ids = []
    failed_namespaces = []

    try:
        # Get namespaces that need breakfast menu notifications right now
        namespace_ids = get_concerned_namespaces(
            db=db, survey_time_field="breakfast_menu_time"
        )

        logger.info(
            f"Found {len(namespace_ids)} namespaces eligible for breakfast notifications"
        )

        if not namespace_ids:
            return TriggerNotificationResponse(
                total_namespaces=0,
                queued_successfully=0,
                failed_to_queue=0,
                task_ids=[],
                failed_namespaces=[],
                message="No namespaces are currently in breakfast menu time window",
            )

        # Publish a job for each namespace
        for ns_id in namespace_ids:
            try:
                logger.info(f"Publishing breakfast menu job for namespace {ns_id}")
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.BREAKFAST_MENU, namespace_id=ns_id
                )
                job_ids.append(job_id)
                logger.info(
                    f"Successfully published job {job_id} for namespace {ns_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to publish breakfast notification job for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )
                failed_namespaces.append({"namespace_id": ns_id, "error": str(e)})

        # Send admin notification if there were publishing failures
        if failed_namespaces:
            logger.warning(
                f"Sending batch failure summary for {len(failed_namespaces)} failed namespaces"
            )
            try:
                send_batch_failure_summary(
                    failed_namespaces=failed_namespaces,
                    task_category="Menu Notification",
                    total_attempted=len(namespace_ids),
                    operation_name="Breakfast Menu Notification Job Publishing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary email: {str(email_error)}"
                )

        queued_count = len(job_ids)
        failed_count = len(failed_namespaces)

        return TriggerNotificationResponse(
            total_namespaces=len(namespace_ids),
            queued_successfully=queued_count,
            failed_to_queue=failed_count,
            task_ids=job_ids,
            failed_namespaces=[f["namespace_id"] for f in failed_namespaces],
            message=f"Queued {queued_count} tasks successfully, {failed_count} failed",
        )

    except Exception as e:
        logger.error(
            f"Error in trigger_breakfast_notifications endpoint: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger breakfast notifications: {str(e)}",
        )


@router.post("/trigger_lunch_notifications", response_model=TriggerNotificationResponse)
def trigger_lunch_notifications(db=Depends(get_db)):
    """
    Trigger lunch menu notifications for all eligible namespaces.

    This endpoint queries all namespaces where it's currently lunch menu time
    and publishes a Pub/Sub job for each namespace to send notifications to eligible guests.

    Returns:
        TriggerNotificationResponse with statistics about published jobs
    """
    logger.info("Lunch notification trigger endpoint called")

    job_ids = []
    failed_namespaces = []

    try:
        # Get namespaces that need lunch menu notifications right now
        namespace_ids = get_concerned_namespaces(
            db=db, survey_time_field="lunch_menu_time"
        )

        logger.info(
            f"Found {len(namespace_ids)} namespaces eligible for lunch notifications"
        )

        if not namespace_ids:
            return TriggerNotificationResponse(
                total_namespaces=0,
                queued_successfully=0,
                failed_to_queue=0,
                task_ids=[],
                failed_namespaces=[],
                message="No namespaces are currently in lunch menu time window",
            )

        # Publish a job for each namespace
        for ns_id in namespace_ids:
            try:
                logger.info(f"Publishing lunch menu job for namespace {ns_id}")
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.LUNCH_MENU, namespace_id=ns_id
                )
                job_ids.append(job_id)
                logger.info(
                    f"Successfully published job {job_id} for namespace {ns_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to publish lunch notification job for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )
                failed_namespaces.append({"namespace_id": ns_id, "error": str(e)})

        # Send admin notification if there were publishing failures
        if failed_namespaces:
            logger.warning(
                f"Sending batch failure summary for {len(failed_namespaces)} failed namespaces"
            )
            try:
                send_batch_failure_summary(
                    failed_namespaces=failed_namespaces,
                    task_category="Menu Notification",
                    total_attempted=len(namespace_ids),
                    operation_name="Lunch Menu Notification Job Publishing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary email: {str(email_error)}"
                )

        queued_count = len(job_ids)
        failed_count = len(failed_namespaces)

        return TriggerNotificationResponse(
            total_namespaces=len(namespace_ids),
            queued_successfully=queued_count,
            failed_to_queue=failed_count,
            task_ids=job_ids,
            failed_namespaces=[f["namespace_id"] for f in failed_namespaces],
            message=f"Queued {queued_count} tasks successfully, {failed_count} failed",
        )

    except Exception as e:
        logger.error(
            f"Error in trigger_lunch_notifications endpoint: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger lunch notifications: {str(e)}",
        )


@router.post(
    "/trigger_dinner_notifications", response_model=TriggerNotificationResponse
)
def trigger_dinner_notifications(db=Depends(get_db)):
    """
    Trigger dinner menu notifications for all eligible namespaces.

    This endpoint queries all namespaces where it's currently dinner menu time
    and publishes a Pub/Sub job for each namespace to send notifications to eligible guests.

    Returns:
        TriggerNotificationResponse with statistics about published jobs
    """
    logger.info("Dinner notification trigger endpoint called")

    job_ids = []
    failed_namespaces = []

    try:
        # Get namespaces that need dinner menu notifications right now
        namespace_ids = get_concerned_namespaces(
            db=db, survey_time_field="dinner_menu_time"
        )

        logger.info(
            f"Found {len(namespace_ids)} namespaces eligible for dinner notifications"
        )

        if not namespace_ids:
            return TriggerNotificationResponse(
                total_namespaces=0,
                queued_successfully=0,
                failed_to_queue=0,
                task_ids=[],
                failed_namespaces=[],
                message="No namespaces are currently in dinner menu time window",
            )

        # Publish a job for each namespace
        for ns_id in namespace_ids:
            try:
                logger.info(f"Publishing dinner menu job for namespace {ns_id}")
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.DINNER_MENU, namespace_id=ns_id
                )
                job_ids.append(job_id)
                logger.info(
                    f"Successfully published job {job_id} for namespace {ns_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to publish dinner notification job for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )
                failed_namespaces.append({"namespace_id": ns_id, "error": str(e)})

        # Send admin notification if there were publishing failures
        if failed_namespaces:
            logger.warning(
                f"Sending batch failure summary for {len(failed_namespaces)} failed namespaces"
            )
            try:
                send_batch_failure_summary(
                    failed_namespaces=failed_namespaces,
                    task_category="Menu Notification",
                    total_attempted=len(namespace_ids),
                    operation_name="Dinner Menu Notification Job Publishing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary email: {str(email_error)}"
                )

        queued_count = len(job_ids)
        failed_count = len(failed_namespaces)

        return TriggerNotificationResponse(
            total_namespaces=len(namespace_ids),
            queued_successfully=queued_count,
            failed_to_queue=failed_count,
            task_ids=job_ids,
            failed_namespaces=[f["namespace_id"] for f in failed_namespaces],
            message=f"Queued {queued_count} tasks successfully, {failed_count} failed",
        )

    except Exception as e:
        logger.error(
            f"Error in trigger_dinner_notifications endpoint: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger dinner notifications: {str(e)}",
        )
