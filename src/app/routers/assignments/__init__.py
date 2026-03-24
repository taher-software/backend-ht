import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.app.db.orm import get_db
from src.app.globals.admin_notifications import send_batch_failure_summary
from src.app.globals.enum import JobType
from src.app.globals.response import ApiResponse
from src.app.globals.generic_responses import validation_response
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.schema_models import Role
from src.app.gcp import pubsub_publisher
from src.app.routers.meals.modelsOut import (
    ReminderBatchResponse,
    QueuedTask,
    FailedNamespace,
)
from .modelsIn import CreatePlanIn
from .services import (
    create_plan,
    get_next_day_by_area,
    get_today_plan_by_area,
    get_namespaces_require_reminder_for_housekeeper_schedule,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"],
    responses={**validation_response},
)

ALLOWED_ROLES = {
    Role.owner.value,
    Role.admin.value,
    Role.supervisor.value,
    Role.housekeeping_supervisor.value,
}


def _check_role(current_user: dict):
    if not set(current_user.get("role", [])) & ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage assignments.",
        )


@router.get("/next_day_by_area")
def next_day_by_area(
    area: str,
    db=Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    _check_role(current_user)
    result = get_next_day_by_area(
        namespace_id=current_user["namespace_id"],
        area=area,
        db=db,
    )
    return ApiResponse(data=result)


@router.get("/today_plan_by_area")
def today_plan_by_area(
    area: str,
    db=Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    _check_role(current_user)
    result = get_today_plan_by_area(
        namespace_id=current_user["namespace_id"],
        area=area,
        db=db,
    )
    return ApiResponse(data=result)


@router.post("/plan")
def create_plan_endpoint(
    payload: CreatePlanIn,
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    _check_role(current_user)
    create_plan(
        namespace_id=current_user["namespace_id"],
        plan_date=payload.plan_date,
        assignments=payload.assignments,
    )
    return ApiResponse(data="Plan created successfully.")


@router.post("/plan_assignments_reminder", response_model=ReminderBatchResponse)
def plan_assignments_reminder(db: Session = Depends(get_db)):
    """
    Publish assignment reminder Pub/Sub jobs for namespaces that have not
    yet planned tomorrow's housekeeper schedule and whose local time is
    still within 6 hours after midday.

    Steps:
        1. Retrieve all qualifying namespaces.
        2. Publish one ASSIGNMENT_REMINDER job per namespace.
        3. If any publish calls fail, send a batch failure summary email.
        4. Return a report with queued tasks and failed namespaces.
    """
    try:
        logger.info(
            "Retrieving namespaces that require housekeeper assignment reminders"
        )

        namespace_ids = get_namespaces_require_reminder_for_housekeeper_schedule(db=db)

        if not namespace_ids:
            logger.info("No namespaces require assignment reminders at this time")
            return ReminderBatchResponse(
                message="No namespaces require assignment reminders",
                total_namespaces=0,
                queued_tasks=[],
                failed_namespaces=[],
            )

        logger.info(
            f"Found {len(namespace_ids)} namespace(s) requiring assignment reminders"
        )

        queued_tasks = []
        failed_namespaces = []

        for ns_id in namespace_ids:
            try:
                job_id = pubsub_publisher.publish_job(
                    job_type=JobType.ASSIGNMENT_REMINDER,
                    namespace_id=ns_id,
                )
                queued_tasks.append(
                    QueuedTask(namespace_id=ns_id, task_id=job_id, status="queued")
                )
                logger.info(
                    f"Published assignment reminder job for namespace {ns_id}: {job_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to publish job for namespace {ns_id}: {e}",
                    exc_info=True,
                )
                failed_namespaces.append(FailedNamespace(namespace_id=ns_id, error=str(e)))

        if failed_namespaces:
            try:
                send_batch_failure_summary(
                    failed_namespaces=[
                        {"namespace_id": f.namespace_id, "error": f.error}
                        for f in failed_namespaces
                    ],
                    task_category="Assignment Reminder",
                    total_attempted=len(namespace_ids),
                    operation_name="Assignment Reminder Queueing",
                )
            except Exception as email_error:
                logger.error(f"Failed to send batch failure summary: {email_error}")

        return ReminderBatchResponse(
            message=f"Published {len(queued_tasks)} assignment reminder job(s)",
            total_namespaces=len(namespace_ids),
            queued_tasks=queued_tasks,
            failed_namespaces=failed_namespaces,
        )

    except Exception as e:
        logger.error(
            f"Critical error in plan_assignments_reminder: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish assignment reminder jobs: {e}",
        )
