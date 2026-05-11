import resend
from src.settings import settings
import logging

resend.api_key = settings.resend_api_key 

logger = logging.getLogger(__name__)

def send_email_with_resend(to_email: str, subject: str, html_content: str, raising: bool = False) -> bool:
    try:
        resend.Emails.send({
            "from": f"{settings.mail_username}",
            "to": to_email,
            "subject": subject,
            "html": html_content
        })

        if not raising:
            return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
        if raising:
            raise e
        return False