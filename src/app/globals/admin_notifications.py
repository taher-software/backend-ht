"""
Admin Notification Module

Sends email notifications to super admins about critical system failures,
particularly for Celery task failures that exhaust retry attempts.

Usage:
    from src.app.globals.admin_notifications import send_admin_failure_notification

    # In a Celery task after max retries
    if self.request.retries >= self.max_retries:
        send_admin_failure_notification(
            namespace_id=123,
            task_name="send_breakfast_reminder",
            meal_type="breakfast",
            error_message=str(exception),
            task_id=self.request.id
        )
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
from datetime import datetime
from src.settings import settings

logger = logging.getLogger(__name__)


def get_super_admin_emails() -> List[str]:
    """
    Get list of super admin email addresses from settings.

    Reads from environment variable 'super_admin_emails' which should be
    a comma-separated list of email addresses.

    Returns:
        List of admin email addresses

    Example:
        ['admin1@bodor.com', 'admin2@bodor.com', 'devops@bodor.com']
    """
    try:
        admin_emails = settings.super_admin_email_list
        if not admin_emails:
            logger.warning("No super admin emails configured, using fallback")
            return [settings.mail_username]  # Fallback to system email

        logger.debug(f"Retrieved {len(admin_emails)} super admin emails")
        return admin_emails

    except Exception as e:
        logger.error(f"Failed to get super admin emails: {str(e)}", exc_info=True)
        # Fallback to system email
        return [settings.mail_username]


def send_admin_failure_notification(
    namespace_id: int,
    task_name: str,
    error_message: str,
    task_id: str,
    task_category: str = "Task",
    additional_context: dict = None,
) -> bool:
    """
    Send email notification to super admins about a critical task failure.

    This is a GENERIC function that can be used for ANY task failure, not just
    meal-specific tasks. It sends ONE email per namespace failure.

    This function is called when a Celery task exhausts all retry attempts
    or when a critical system error occurs.

    Args:
        namespace_id: ID of the namespace that failed (0 for global/system failures)
        task_name: Name of the failed task (e.g., "send_breakfast_reminder")
        error_message: Detailed error message from the exception
        task_id: Celery task ID for tracing
        task_category: Category of task (e.g., "Meal Reminder", "Survey", "Notification")
        additional_context: Optional dict with extra context to display in email

    Returns:
        True if email sent successfully to at least one admin, False otherwise

    Example (Meal Reminder):
        send_admin_failure_notification(
            namespace_id=123,
            task_name="send_notif_breakfast_menu_reminder_for_namespace",
            error_message="Connection timeout to notification service",
            task_id="abc-123-def-456",
            task_category="Meal Reminder",
            additional_context={"meal_type": "breakfast", "managers_count": 5}
        )

    Example (Survey Task):
        send_admin_failure_notification(
            namespace_id=456,
            task_name="send_room_satisfaction_survey",
            error_message="Database connection timeout",
            task_id="xyz-789-abc",
            task_category="Survey",
            additional_context={"survey_type": "room_satisfaction", "guests_count": 10}
        )

    Example (Global Failure):
        send_admin_failure_notification(
            namespace_id=0,
            task_name="cleanup_expired_sessions",
            error_message="Redis connection lost",
            task_id="global-123",
            task_category="System Maintenance"
        )
    """
    try:
        # Get admin email addresses
        admin_emails = get_super_admin_emails()

        if not admin_emails:
            logger.error("No admin emails available, cannot send notification")
            return False

        # Prepare email content
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Determine failure scope
        failure_scope = (
            "Global System Failure"
            if namespace_id == 0
            else f"Namespace {namespace_id}"
        )

        # Build additional context HTML if provided
        context_rows = ""
        if additional_context:
            for key, value in additional_context.items():
                # Format key: convert snake_case to Title Case
                formatted_key = key.replace("_", " ").title()
                context_rows += f"""
                <tr>
                    <td>{formatted_key}:</td>
                    <td>{value}</td>
                </tr>
                """

        # Create HTML email content
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background-color: #dc3545;
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .content {{
            padding: 30px;
        }}
        .alert-box {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-bottom: 20px;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .info-table td {{
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .info-table td:first-child {{
            font-weight: bold;
            width: 150px;
            color: #555;
        }}
        .error-box {{
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 4px;
            padding: 15px;
            margin: 20px 0;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #721c24;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .action-required {{
            background-color: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 15px;
            margin: 20px 0;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-critical {{
            background-color: #dc3545;
            color: white;
        }}
        .badge-category {{
            background-color: #17a2b8;
            color: white;
        }}
        .context-section {{
            background-color: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 CRITICAL: Task Failure Alert</h1>
        </div>

        <div class="content">
            <div class="alert-box">
                <strong>⚠️ A critical failure occurred in the {task_category} system.</strong>
                <br>
                This notification was sent because the task exhausted all retry attempts.
            </div>

            <table class="info-table">
                <tr>
                    <td>Failure Scope:</td>
                    <td><span class="badge badge-critical">{failure_scope}</span></td>
                </tr>
                <tr>
                    <td>Namespace ID:</td>
                    <td>{namespace_id}</td>
                </tr>
                <tr>
                    <td>Task Category:</td>
                    <td><span class="badge badge-category">{task_category}</span></td>
                </tr>
                <tr>
                    <td>Task Name:</td>
                    <td>{task_name}</td>
                </tr>
                <tr>
                    <td>Task ID:</td>
                    <td><code>{task_id}</code></td>
                </tr>
                <tr>
                    <td>Timestamp:</td>
                    <td>{timestamp}</td>
                </tr>
            </table>

            {f'<div class="context-section"><h3>Additional Context:</h3><table class="info-table">{context_rows}</table></div>' if context_rows else ''}

            <h3>Error Details:</h3>
            <div class="error-box">{error_message}</div>

            <div class="action-required">
                <h3>📋 Action Required:</h3>
                <ul>
                    <li>Investigate the namespace configuration and task logs</li>
                    <li>Check Cloud Pub/Sub and Cloud Tasks queue health in GCP Console</li>
                    <li>Verify worker endpoint status ({settings.worker_url if hasattr(settings, 'worker_url') else '/worker'})</li>
                    <li>Verify service connectivity (notification, database, etc.)</li>
                    <li>Review recent changes to the {task_category} system</li>
                    <li>Check GCP service account permissions</li>
                    <li>Manually retry the task if needed</li>
                </ul>
            </div>
        <div class="footer">
            <p><strong>Bodor Notification System</strong></p>
            <p>This is an automated notification from the Bodor notification system.</p>
            <p>Powered by Google Cloud Pub/Sub and Cloud Tasks</p>
            <p>Generated at {timestamp}</p>
        </div>
    </div>
</body>
</html>
"""

        # Create message for each admin
        subject = f"[CRITICAL] {task_category} Task Failed - {failure_scope}"

        # Send to all admins
        success_count = 0
        for admin_email in admin_emails:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = settings.mail_username
                msg["To"] = admin_email

                # Attach HTML content
                msg.attach(MIMEText(html_content, "html"))

                # Send via SMTP
                smtp = smtplib.SMTP("smtp.gmail.com", 587)
                smtp.starttls()
                smtp.login(settings.mail_username, settings.mail_pwd)
                smtp.sendmail(settings.mail_username, admin_email, msg.as_string())
                smtp.quit()

                success_count += 1
                logger.info(
                    f"Sent admin failure notification to {admin_email} "
                    f"for task {task_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to send admin notification to {admin_email}: {str(e)}",
                    exc_info=True,
                )

        # Return success if at least one email was sent
        if success_count > 0:
            logger.info(
                f"Successfully sent admin notifications to {success_count}/{len(admin_emails)} admins"
            )
            return True
        else:
            logger.error("Failed to send admin notifications to any recipient")
            return False

    except Exception as e:
        logger.error(
            f"Critical error in send_admin_failure_notification: {str(e)}",
            exc_info=True,
        )
        return False


def send_batch_failure_summary(
    failed_namespaces: List[dict],
    task_category: str,
    total_attempted: int,
    operation_name: str = "Task Queueing",
) -> bool:
    """
    Send a summary email about multiple namespace failures.

    This is a GENERIC function for reporting batch failures across any task type.
    Used when an endpoint fails to queue tasks for multiple namespaces.

    Args:
        failed_namespaces: List of dicts with 'namespace_id' and 'error'
        task_category: Category of task (e.g., "Meal Reminder", "Survey", "Notification")
        total_attempted: Total number of namespaces attempted
        operation_name: Name of the operation (e.g., "Task Queueing", "Batch Processing")

    Returns:
        True if email sent successfully to at least one admin, False otherwise

    Example (Meal Reminder):
        send_batch_failure_summary(
            failed_namespaces=[
                {"namespace_id": 123, "error": "Connection timeout"},
                {"namespace_id": 456, "error": "Invalid configuration"}
            ],
            task_category="Meal Reminder",
            total_attempted=10,
            operation_name="Breakfast Reminder Queueing"
        )

    Example (Survey):
        send_batch_failure_summary(
            failed_namespaces=[
                {"namespace_id": 789, "error": "No guests found"}
            ],
            task_category="Survey",
            total_attempted=5,
            operation_name="Room Survey Batch"
        )
    """
    if not failed_namespaces:
        return True  # No failures to report

    try:
        admin_emails = get_super_admin_emails()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Build failure list HTML
        failure_rows = ""
        for failure in failed_namespaces:
            failure_rows += f"""
            <tr>
                <td>{failure['namespace_id']}</td>
                <td>{failure['error']}</td>
            </tr>
            """

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
        .container {{ max-width: 700px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background-color: #ffc107; color: #333; padding: 20px; text-align: center; }}
        .content {{ padding: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background-color: #f8f9fa; padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; }}
        td {{ padding: 10px; border-bottom: 1px solid #e0e0e0; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; background-color: #17a2b8; color: white; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Batch {operation_name} Failures</h1>
        </div>
        <div class="content">
            <p><strong>Multiple namespaces failed during {operation_name}.</strong></p>
            <p><strong>Task Category:</strong> <span class="badge">{task_category}</span></p>
            <p><strong>Summary:</strong></p>
            <ul>
                <li>Total Attempted: {total_attempted}</li>
                <li>Failed: {len(failed_namespaces)}</li>
                <li>Succeeded: {total_attempted - len(failed_namespaces)}</li>
                <li>Success Rate: {((total_attempted - len(failed_namespaces)) / total_attempted * 100):.1f}%</li>
            </ul>
            <h3>Failed Namespaces:</h3>
            <table>
                <tr>
                    <th>Namespace ID</th>
                    <th>Error</th>
                </tr>
                {failure_rows}
            </table>
            <p><em>Timestamp: {timestamp}</em></p>
        </div>
    </div>
</body>
</html>
"""

        subject = f"[WARNING] Batch {task_category} {operation_name} Failures"

        success_count = 0
        for admin_email in admin_emails:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = settings.mail_username
                msg["To"] = admin_email
                msg.attach(MIMEText(html_content, "html"))

                smtp = smtplib.SMTP("smtp.gmail.com", 587)
                smtp.starttls()
                smtp.login(settings.mail_username, settings.mail_pwd)
                smtp.sendmail(settings.mail_username, admin_email, msg.as_string())
                smtp.quit()

                success_count += 1
                logger.info(f"Sent batch failure summary to {admin_email}")

            except Exception as e:
                logger.error(f"Failed to send batch summary to {admin_email}: {str(e)}")

        return success_count > 0

    except Exception as e:
        logger.error(f"Error in send_batch_failure_summary: {str(e)}", exc_info=True)
        return False
