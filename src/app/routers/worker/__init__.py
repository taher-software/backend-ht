from fastapi import APIRouter, Body, HTTPException
import base64
import json
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from src.app.globals.enum import JobType, CachingCollectionName
from src.app.gcp import firestore_client
import logging
from datetime import datetime
from .modelsIn import PubSubMessage, JobPayload, CloudTaskPayload

# Import all task handlers
from src.async_jobs.tasks.daily_room_survey import (
    send_notif_daily_room_satisf_for_namespace,
)
from src.async_jobs.tasks.restaurant_survey import (
    send_notif_restaurant_survey_for_namespace,
)
from src.async_jobs.tasks.room_reception import (
    send_notif_room_reception_satisf_for_guest,
)
from src.async_jobs.tasks.meals_notifs import (
    send_notif_breakfast_menu_for_namespace,
    send_notif_lunch_menu_for_namespace,
    send_notif_dinner_menu_for_namespace,
)
from src.async_jobs.tasks.add_meals_reminder import (
    send_notif_breakfast_menu_reminder_for_namespace,
    send_notif_lunch_menu_reminder_for_namespace,
    send_notif_dinner_menu_reminder_for_namespace,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Worker"], responses={**validation_response})

# Map job types to their corresponding task handlers
JOB_HANDLERS = {
    JobType.DAILY_ROOM_SURVEY: send_notif_daily_room_satisf_for_namespace,
    JobType.RESTAURANT_SURVEY: send_notif_restaurant_survey_for_namespace,
    JobType.ROOM_RECEPTION_SURVEY: send_notif_room_reception_satisf_for_guest,
    JobType.BREAKFAST_MENU: send_notif_breakfast_menu_for_namespace,
    JobType.LUNCH_MENU: send_notif_lunch_menu_for_namespace,
    JobType.DINNER_MENU: send_notif_dinner_menu_for_namespace,
    JobType.BREAKFAST_REMINDER: send_notif_breakfast_menu_reminder_for_namespace,
    JobType.LUNCH_REMINDER: send_notif_lunch_menu_reminder_for_namespace,
    JobType.DINNER_REMINDER: send_notif_dinner_menu_reminder_for_namespace,
}


def check_task_already_processed(job_id: str, collection_name: str) -> bool:
    """
    Check if a task has already been processed using Firestore.

    Args:
        job_id: Unique identifier for the task (used as document ID)
        collection_name: Collection name for the worker type

    Returns:
        bool: True if task already processed, False otherwise
    """
    try:
        existing_doc = firestore_client.get_document(
            collection_name=collection_name, document_id=job_id
        )
        return existing_doc is not None
    except Exception as e:
        logger.error(f"Error checking task deduplication for job {job_id}: {str(e)}")
        # On error, allow processing to continue (fail open)
        return False


def mark_task_as_processed(
    job_id: str,
    collection_name: str,
    job_type: JobType,
    namespace_id: int = None,
    guest_id: str = None,
) -> str:
    """
    Mark a task as processed in Firestore to prevent duplicate execution.
    Uses job_id as the document ID for efficient lookups.

    Args:
        job_id: Unique identifier for the task (used as document ID)
        collection_name: Collection name for the worker type
        job_type: Type of the job being processed
        namespace_id: Optional namespace ID
        guest_id: Optional guest ID

    Returns:
        str: The document ID (same as job_id)
    """
    try:
        doc_data = {
            "job_type": job_type.value,
            "processed_at": datetime.utcnow().isoformat(),
        }

        if namespace_id is not None:
            doc_data["namespace_id"] = namespace_id

        if guest_id is not None:
            doc_data["guest_id"] = guest_id

        # Create document with job_id as the document ID
        collection_ref = firestore_client.client.collection(collection_name)
        collection_ref.document(job_id).set(doc_data)

        logger.info(
            f"[Job {job_id}] Marked as processed in Firestore collection '{collection_name}'"
        )
        return job_id
    except Exception as e:
        logger.error(f"Error marking task as processed for job {job_id}: {str(e)}")
        raise


def remove_task_marker(job_id: str, collection_name: str):
    """
    Remove a task marker from Firestore when task execution fails.

    Args:
        job_id: Unique identifier for the task (document ID)
        collection_name: Collection name for the worker type
    """
    try:
        firestore_client.delete_document(
            collection_name=collection_name, document_id=job_id
        )
        logger.info(f"[Job {job_id}] Removed task marker from Firestore after failure")
    except Exception as e:
        logger.error(f"Error removing task marker for job {job_id}: {str(e)}")


@router.post("/", response_model=ApiResponse)
async def pubsub_entrypoint(pubsub_data: PubSubMessage):
    """
    Cloud Pub/Sub Push endpoint.

    Receives a Pub/Sub message → decodes → routes to the appropriate job handler.

    Pub/Sub sends:
    {
       "message": {
          "data": "Base64EncodedString",
          "messageId": "...",
          "publishTime": "..."
       },
       "subscription": "projects/.../subscriptions/..."
    }
    """

    try:
        # --- 1. Decode the Base64 payload sent by Pub/Sub ---
        encoded_data = pubsub_data.message.get("data")
        if not encoded_data:
            raise ValueError("Missing 'data' field in Pub/Sub message")

        try:
            decoded_bytes = base64.b64decode(encoded_data)
            payload_dict = json.loads(decoded_bytes)
        except Exception:
            raise ValueError("Invalid Base64 or JSON data")

        # --- 2. Validate your business payload ---
        job = JobPayload(**payload_dict)

        logger.info(
            f"[Job {job.job_id}] Received Pub/Sub job: "
            f"type={job.job_type}, namespace={job.namespace_id}, "
            f"messageId={pubsub_data.message.get('messageId')}"
        )

        # --- 3. Check for duplicate task execution ---
        collection_name = CachingCollectionName.PROCESSED_PUBSUB_TASKS
        if check_task_already_processed(job.job_id, collection_name):
            logger.warning(
                f"[Job {job.job_id}] Task already being processed by another worker, rejecting duplicate"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Task {job.job_id} already being processed by another worker",
            )

        # --- 4. Mark task as being processed ---
        mark_task_as_processed(
            job_id=job.job_id,
            collection_name=collection_name,
            job_type=job.job_type,
            namespace_id=job.namespace_id,
        )

        # --- 6. Execute the async job ---
        try:
            # --- 5. Find the appropriate job handler ---
            handler = JOB_HANDLERS.get(job.job_type)
            if not handler:
                raise ValueError(f"Unknown job type: {job.job_type}")
            result = handler(namespace_id=job.namespace_id, job_id=job.job_id)

            logger.info(
                f"[Job {job.job_id}] Completed: type={job.job_type}, namespace={job.namespace_id}"
            )

            # --- 7. Pub/Sub expects HTTP 200 to ACK the message ---
            return ApiResponse(
                data={
                    "message": "Job executed successfully",
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "namespace_id": job.namespace_id,
                    "result": result,
                }
            )

        except Exception as task_error:
            # Remove task marker on failure to allow retry
            logger.error(
                f"[Job {job.job_id}] Task execution failed, removing task marker: {str(task_error)}"
            )
            remove_task_marker(job.job_id, collection_name)
            raise

    except Exception as e:
        logger.error(
            f"[Job ERROR] Failure processing message: error={e}",
            exc_info=True,
        )
        # Pub/Sub will retry automatically if we return a non-2xx
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cloud_job", response_model=ApiResponse)
async def cloud_task_entrypoint(task_data: CloudTaskPayload):
    """
    Cloud Tasks HTTP endpoint.

    Receives a Cloud Task HTTP request → validates → routes to job handler.

    Cloud Tasks sends direct JSON payload (not Base64 encoded like Pub/Sub):
    {
       "job_id": "uuid-string",
       "job_type": "DAILY_ROOM_SURVEY",
       "namespace_id": 123
    }
    """

    try:
        logger.info(
            f"[Job {task_data.job_id}] Received Cloud Task: "
            f"type={task_data.job_type}, namespace={task_data.namespace_id}"
        )

        # Check for duplicate task execution
        collection_name = CachingCollectionName.PROCESSED_CLOUD_TASKS
        if check_task_already_processed(task_data.job_id, collection_name):
            logger.warning(
                f"[Job {task_data.job_id}] Task already being processed by another worker, rejecting duplicate"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Task {task_data.job_id} already being processed by another worker",
            )

        # Mark task as being processed
        mark_task_as_processed(
            job_id=task_data.job_id,
            collection_name=collection_name,
            job_type=task_data.job_type,
            namespace_id=task_data.namespace_id,
            guest_id=task_data.guest_id,
        )

        # Execute the async job with optional guest_id
        try:
            # Find the appropriate job handler
            handler = JOB_HANDLERS.get(task_data.job_type)
            if not handler:
                raise ValueError(f"Unknown job type: {task_data.job_type}")
            if task_data.guest_id:
                result = handler(
                    job_id=task_data.job_id,
                    guest_id=task_data.guest_id,
                    namespace_id=task_data.namespace_id,
                )
            else:
                result = handler(
                    namespace_id=task_data.namespace_id, job_id=task_data.job_id
                )

            logger.info(
                f"[Job {task_data.job_id}] Completed: type={task_data.job_type}, namespace={task_data.namespace_id}"
            )

            # Cloud Tasks expects HTTP 200 to mark task as successful
            return ApiResponse(
                data={
                    "message": "Job executed successfully",
                    "job_id": task_data.job_id,
                    "job_type": task_data.job_type,
                    "namespace_id": task_data.namespace_id,
                    "result": result,
                }
            )

        except Exception as task_error:
            # Remove task marker on failure to allow retry
            logger.error(
                f"[Job {task_data.job_id}] Task execution failed, removing task marker: {str(task_error)}"
            )
            remove_task_marker(task_data.job_id, collection_name)
            raise

    except Exception as e:
        logger.error(
            f"[Job ERROR] Failure processing Cloud Task: error={e}",
            exc_info=True,
        )
        # Cloud Tasks will retry automatically if we return a non-2xx
        raise HTTPException(status_code=500, detail=str(e))
