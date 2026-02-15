from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import logging

from src.app.db.orm import get_db
from src.app.globals.authentication import CurrentUserIdentifier
from .services import (
    get_prioritized_survey,
    submit_survey as submit_survey_service,
    submit_dishes_survey,
    get_all_active_namespaces,
)
from .modelsOut import SurveyResponse
from .modelsIn import SubmitSurveyPayload, DishesSurveySubmitPayload
from src.app.globals.response import ApiResponse
from src.app.db.models import Namespace
from src.app.globals.admin_notifications import send_batch_failure_summary
from src.app.gcp import pubsub_publisher
from src.app.globals.enum import JobType
from src.async_jobs.tasks.utils import get_concerned_namespaces

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/surveys",
    tags=["surveys"],
)


@router.get("/", response_model=SurveyResponse)
def get_latest_surveys(
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier("guest")),
):
    """Get prioritized survey"""
    survey = get_prioritized_survey(db, current_user)
    if not survey:
        raise HTTPException(status_code=404, detail="No survey available at this time")
    return SurveyResponse(**survey)


@router.post("/submit")
def submit_survey(
    payload: SubmitSurveyPayload = Body(...),
    current_guest: dict = Depends(CurrentUserIdentifier(who="guest")),
    response_model=ApiResponse,  # Adjust as needed for your response model
) -> ApiResponse:
    """Submit a survey"""
    return submit_survey_service(payload, current_guest)


@router.post("/dishes_survey/submit")
def submit_dishes_survey_endpoint(
    payload: DishesSurveySubmitPayload = Body(...),
    db: Session = Depends(get_db),
    current_guest: dict = Depends(CurrentUserIdentifier("guest")),
):
    """Submit a dishes survey"""
    return submit_dishes_survey(payload, current_guest, db)


@router.post("/trigger-restaurant-survey")
def trigger_restaurant_survey_notifications(
    db: Session = Depends(get_db),
):
    """
    Manually trigger restaurant survey notifications for all namespaces.

    This endpoint publishes Pub/Sub jobs for each namespace to send restaurant
    survey notifications to eligible guests. Each namespace is processed independently
    with retry capabilities and failure notifications.

    Returns:
        ApiResponse with queuing statistics including:
        - total_namespaces: Total number of namespaces in the system
        - queued_successfully: Number of jobs successfully queued
        - failed_to_queue: Number of namespaces that failed to queue
        - failed_namespace_ids: List of namespace IDs that failed

    Raises:
        HTTPException: If there's a database error or critical failure
    """

    try:

        # Query all namespaces
        namespaces_ids = get_concerned_namespaces(
            survey_time_field="restaurant_survey_time", db=db
        )
        total_namespaces = len(namespaces_ids)

        if total_namespaces == 0:
            logger.info("No namespaces found in database")
            return ApiResponse(
                data={
                    "total_namespaces": 0,
                    "queued_successfully": 0,
                    "failed_to_queue": 0,
                    "failed_namespace_ids": [],
                    "message": "No namespaces found to process",
                }
            )

        logger.info(f"Found {total_namespaces} namespaces to process")

        # Track successes and failures
        queued_successfully = 0
        failed_namespaces = []

        # Publish job for each namespace
        for ns_id in namespaces_ids:
            try:
                # Publish the per-namespace job to Pub/Sub
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.RESTAURANT_SURVEY, namespace_id=ns_id
                )
                queued_successfully += 1
                logger.info(
                    f"Successfully published restaurant survey job {job_id} for namespace {ns_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to queue restaurant survey task for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )
                failed_namespaces.append({"namespace_id": ns_id, "error": str(e)})

        # If any failures occurred, send batch failure summary to admins
        if failed_namespaces:
            logger.warning(
                f"Failed to queue tasks for {len(failed_namespaces)} namespace(s), sending admin notification"
            )
            try:
                send_batch_failure_summary(
                    failed_namespaces=failed_namespaces,
                    task_category="Survey",
                    total_attempted=total_namespaces,
                    operation_name="Restaurant Survey Queueing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary email: {str(email_error)}",
                    exc_info=True,
                )

        # Prepare response
        response_data = {
            "total_namespaces": total_namespaces,
            "queued_successfully": queued_successfully,
            "failed_to_queue": len(failed_namespaces),
            "failed_namespace_ids": [f["namespace_id"] for f in failed_namespaces],
        }

        if failed_namespaces:
            message = (
                f"Restaurant survey tasks queued for {queued_successfully}/{total_namespaces} namespaces. "
                f"{len(failed_namespaces)} namespace(s) failed. Admin notification sent."
            )
        else:
            message = f"Restaurant survey tasks successfully queued for all {total_namespaces} namespace(s)."

        logger.info(
            f"Restaurant survey trigger completed: {queued_successfully} queued, {len(failed_namespaces)} failed"
        )
        response_data["message"] = message

        return ApiResponse(data=response_data)

    except Exception as e:
        logger.error(
            f"Critical error in trigger_restaurant_survey_notifications: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger restaurant survey notifications: {str(e)}",
        )


@router.post("/trigger-daily-survey")
def trigger_daily_room_survey(
    db: Session = Depends(get_db),
):
    """
    Manually trigger daily room satisfaction survey notifications for all active namespaces.

    This endpoint publishes Pub/Sub jobs for each namespace with active guests
    to send daily room satisfaction survey notifications. Each namespace is processed
    independently with retry capabilities and failure notifications.

    Returns:
        ApiResponse with queuing statistics including:
        - total_namespaces: Total number of namespaces with active guests
        - queued_successfully: Number of tasks successfully queued
        - failed_to_queue: Number of namespaces that failed to queue
        - failed_namespace_ids: List of namespace IDs that failed

    Raises:
        HTTPException: If there's a database error or critical failure
    """

    try:
        # Step 1: Get all namespaces with active guests
        logger.info("Retrieving namespaces for daily room survey notifications")

        namespace_ids = get_concerned_namespaces(db=db)

        if not namespace_ids:
            logger.info("No namespaces with active guests found")
            return ApiResponse(
                data={
                    "total_namespaces": 0,
                    "queued_successfully": 0,
                    "failed_to_queue": 0,
                    "failed_namespace_ids": [],
                },
                message="No namespaces with active guests require room surveys",
            )

        logger.info(
            f"Found {len(namespace_ids)} namespaces with active guests for room surveys"
        )

        # Step 2: Queue a task for each namespace
        queued_successfully = 0
        failed_namespaces = []

        for ns_id in namespace_ids:
            try:
                # Publish the per-namespace job to Pub/Sub
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.DAILY_ROOM_SURVEY, namespace_id=ns_id
                )
                queued_successfully += 1
                logger.info(
                    f"Successfully published daily room survey job {job_id} for namespace {ns_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to queue daily room survey task for namespace {ns_id}: {str(e)}",
                    exc_info=True,
                )
                failed_namespaces.append({"namespace_id": ns_id, "error": str(e)})

        # Step 3: Send batch failure summary if there were queueing failures
        if failed_namespaces:
            logger.warning(
                f"Failed to queue tasks for {len(failed_namespaces)} namespace(s), sending admin notification"
            )
            try:
                send_batch_failure_summary(
                    failed_namespaces=failed_namespaces,
                    task_category="Survey",
                    total_attempted=len(namespace_ids),
                    operation_name="Daily Room Survey Queueing",
                )
            except Exception as email_error:
                logger.error(
                    f"Failed to send batch failure summary email: {str(email_error)}",
                    exc_info=True,
                )

        # Step 4: Prepare response
        response_data = {
            "total_namespaces": len(namespace_ids),
            "queued_successfully": queued_successfully,
            "failed_to_queue": len(failed_namespaces),
            "failed_namespace_ids": [f["namespace_id"] for f in failed_namespaces],
        }

        if failed_namespaces:
            message = (
                f"Daily room survey tasks queued for {queued_successfully}/{len(namespace_ids)} namespaces. "
                f"{len(failed_namespaces)} namespace(s) failed. Admin notification sent."
            )
        else:
            message = f"Daily room survey tasks successfully queued for all {len(namespace_ids)} namespace(s)."

        logger.info(
            f"Daily room survey trigger completed: {queued_successfully} queued, {len(failed_namespaces)} failed"
        )

        response_data["message"] = message

        return ApiResponse(data=response_data)

    except Exception as e:
        logger.error(
            f"Critical error in trigger_daily_room_survey endpoint: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger daily room survey notifications: {str(e)}",
        )
