from pydantic import EmailStr, HttpUrl, Field
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from openai import OpenAI
from google.cloud import pubsub_v1
from google.api_core import exceptions as gcp_exceptions
import google.auth
import requests
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def detect_gcp_project_id() -> Optional[str]:
    """
    Automatically detect Google Cloud Project ID using default service account.

    Returns:
        str: The detected project ID, or None if not found
    """

    # Method : Try to get from default credentials
    try:
        _, project_id = google.auth.default()
        if project_id:
            logger.info(
                f"GCP project ID detected from default credentials: {project_id}"
            )
            return project_id
    except Exception as e:
        logger.debug(f"Could not detect project ID from default credentials: {e}")

    return None


class Settings(BaseSettings):
    default_profile: str = (
        "https://static.vecteezy.com/system/resources/thumbnails/009/734/564/small/default-avatar-profile-icon-of-social-media-user-vector.jpg"
    )
    mail_username: EmailStr = Field(env="mail_username")
    mail_pwd: str = Field(env="mail_pwd")
    application_url: HttpUrl = Field(env="application_url")
    jwt_access_expires: int
    jwt_algorithm: str = Field(env="jwt_algorithm")
    db_url: str = Field(env="db_url")
    jwt_secret: str = Field(env="jwt_secret")
    openia_apikey: str = Field(
        env="openia_apikey",
    )
    email_confirmation_router: str = Field(
        env="email_confirmation_router", default="email-confirmation/"
    )

    # Super admin email addresses for critical notifications (comma-separated)
    super_admin_emails: str = Field(
        env="super_admin_emails", default="admin@example.com"
    )

    # Commercial team email addresses for account review notifications (comma-separated)
    commercial_emails: str = Field(
        env="commercial_emails", default="commercial@example.com"
    )

    # Google Cloud Project ID (optional, auto-detected if not provided)
    gcp_project_id: Optional[str] = Field(default=None)

    # Worker URL for Cloud Tasks (base URL without endpoint suffix)
    worker_url: Optional[str] = Field(env="worker_url", default=None)

    # Mobile app configuration
    app_store_app_name: Optional[str] = Field(env="app_store_app_name", default=None)
    play_store_app_name: Optional[str] = Field(env="play_store_app_name", default=None)
    app_store_url: Optional[HttpUrl] = Field(env="app_store_url", default=None)
    play_store_url: Optional[HttpUrl] = Field(env="play_store_url", default=None)

    model_config = SettingsConfigDict(
        env_file=os.getenv("env_file", "./.env"), extra="allow"
    )

    @property
    def super_admin_email_list(self) -> list[str]:
        """Parse comma-separated admin emails into a list"""
        return [
            email.strip()
            for email in self.super_admin_emails.split(",")
            if email.strip()
        ]

    @property
    def commercial_email_list(self) -> list[str]:
        """Parse comma-separated commercial emails into a list"""
        return [
            email.strip()
            for email in self.commercial_emails.split(",")
            if email.strip()
        ]

    @property
    def google_project_id(self) -> Optional[str]:
        """
        Get Google Cloud Project ID.

        Returns the explicitly configured project ID if available,
        otherwise attempts to auto-detect it.
        """
        if self.gcp_project_id:
            return self.gcp_project_id
        return detect_gcp_project_id()


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()


@lru_cache
def initialize_openAI_client():
    client = OpenAI(api_key=settings.openia_apikey)
    return client


# os.environ["OPENAI_API_KEY"] = settings.openia_apikey

client = initialize_openAI_client()
