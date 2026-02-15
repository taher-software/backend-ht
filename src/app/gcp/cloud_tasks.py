import logging
from google.cloud import tasks_v2
from google.api_core import exceptions as gcp_exceptions
from src.settings import settings
import json
import uuid
from datetime import datetime, timezone, timedelta
from src.app.globals.enum import JobType

logger = logging.getLogger(__name__)


class CloudTask:
    """
    Google Cloud Tasks manager for scheduling delayed task execution.

    This class provides an interface to create and manage Cloud Tasks queues
    and schedule tasks with configurable delays.
    """

    def __init__(self, queue_name: str, location: str = "us-central1"):
        """
        Initialize Cloud Tasks client and create/verify queue.

        Args:
            queue_name: Name of the queue to create/use
            location: GCP region for the queue (default: 'us-central1')
        """
        self.client = tasks_v2.CloudTasksClient()
        self.location = location
        self.queue_path = self._create_queue_path(queue_name)

    def _create_queue_path(self, queue_name: str) -> str:
        """
        Private method to create queue if it doesn't exist.

        Creates the queue only if it doesn't exist. Properly distinguishes between
        different failure reasons (NotFound vs PermissionDenied, NetworkError, etc.)

        Args:
            queue_name: Name of the queue

        Returns:
            str: Full queue path (projects/PROJECT_ID/locations/LOCATION/queues/QUEUE_NAME)

        Raises:
            ValueError: If Google Project ID is not configured
            PermissionDenied: If lacking permissions to access/create queue
            Unauthenticated: If authentication fails
            DeadlineExceeded: If request times out
        """
        if not settings.google_project_id:
            logger.warning(
                "Google Project ID is not set. Skipping Cloud Tasks queue initialization."
            )
            raise ValueError("Google Project ID is not set.")

        # Build the queue path
        queue_path = self.client.queue_path(
            settings.google_project_id, self.location, queue_name
        )

        try:
            # Try to get the queue to check if it exists
            self.client.get_queue(request={"name": queue_path})
            logger.info(f"Cloud Tasks queue {queue_path} already exists.")
            return queue_path

        except gcp_exceptions.NotFound:
            # Queue doesn't exist - this is the ONLY case where we should create it
            try:
                parent = self.client.common_location_path(
                    settings.google_project_id, self.location
                )
                queue = tasks_v2.Queue(name=queue_path)
                self.client.create_queue(request={"parent": parent, "queue": queue})
                logger.info(f"Successfully created Cloud Tasks queue: {queue_path}")
                return queue_path

            except gcp_exceptions.AlreadyExists:
                # Race condition: queue was created between our check and create attempt
                logger.info(
                    f"Cloud Tasks queue {queue_path} already exists (created concurrently)."
                )
                return queue_path

            except gcp_exceptions.PermissionDenied as e:
                logger.error(f"Permission denied when creating queue {queue_path}: {e}")
                raise

            except Exception as e:
                logger.error(f"Failed to create Cloud Tasks queue {queue_path}: {e}")
                raise

        except gcp_exceptions.PermissionDenied as e:
            # Permission error when checking - don't try to create, just raise
            logger.error(f"Permission denied when accessing queue {queue_path}: {e}")
            raise

        except gcp_exceptions.Unauthenticated as e:
            # Authentication error - credentials issue
            logger.error(f"Authentication failed when accessing Cloud Tasks: {e}")
            raise

        except gcp_exceptions.DeadlineExceeded as e:
            # Timeout error - network or service issue
            logger.error(f"Timeout when accessing queue {queue_path}: {e}")
            raise

        except Exception as e:
            # Any other unexpected error - log and raise
            logger.error(f"Unexpected error when accessing queue {queue_path}: {e}")
            raise

    def create_task(
        self, delay: int, namespace_id: int, job_type: JobType, guest_id: str = None
    ) -> str:
        """
        Schedule a task with specified delay.

        Args:
            delay: Delay in seconds before task execution (max: 30 days = 2,592,000 seconds)
            namespace_id: Namespace ID to process
            job_type: Type of job from JobType enum
            guest_id: Optional guest ID (phone number) for guest-specific tasks

        Returns:
            str: Task ID (UUID)

        Raises:
            ValueError: If delay is invalid or worker_url is not configured
        """
        # Validate delay
        MAX_DELAY = 2592000  # 30 days in seconds
        if delay < 0:
            raise ValueError("Delay must be non-negative")
        if delay > MAX_DELAY:
            raise ValueError(f"Delay cannot exceed {MAX_DELAY} seconds (30 days)")

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Calculate schedule time
        schedule_time = datetime.now(timezone.utc) + timedelta(seconds=delay)

        # Build task payload (matches CloudTaskPayload schema)
        payload = {
            "job_id": task_id,
            "job_type": job_type.value,
            "namespace_id": namespace_id,
        }

        # Add guest_id if provided
        if guest_id:
            payload["guest_id"] = guest_id

        # Construct the task
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{settings.worker_url}/cloud_job",
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload).encode("utf-8"),
            ),
            schedule_time=schedule_time,
        )

        # Submit the task to the queue
        try:
            self.client.create_task(request={"parent": self.queue_path, "task": task})
            logger.info(
                f"Created task {task_id} (type={job_type.value}, namespace={namespace_id}, "
                f"delay={delay}s, schedule_time={schedule_time.isoformat()})"
            )
            return task_id

        except Exception as e:
            logger.error(
                f"Failed to create task {task_id} (type={job_type.value}, namespace={namespace_id}): {e}",
                exc_info=True,
            )
            raise
