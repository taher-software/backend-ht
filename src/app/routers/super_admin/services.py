from src.app.db.orm import get_db
from src.app.resourcesController import (
    users_controller,
    namespace_controller,
)
from src.app.globals.exceptions import ApiException
from .modelsOut import (
    namespace_not_found_error,
    user_not_found_error,
    user_namespace_mismatch_error,
)
from src.app.globals.emails import send_email, send_account_rejection_email
from src.app.secrets.jwt import sign_jwt
from src.settings import settings
from fastapi import status
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def check_account_data(func):
    @wraps(func)
    def wrapper(hotel_name: str, user_email: str, country: str, city: str, db):
        # Retrieve namespace by hotel_name, country, and city
        namespace = namespace_controller.find_by_params(
            {"hotel_name": hotel_name, "country": country, "city": city}, db=db
        )

        if not namespace:
            raise ApiException(status.HTTP_404_NOT_FOUND, namespace_not_found_error)

        # Retrieve user by email
        user = users_controller.find_by_params({"user_email": user_email}, db=db)

        if not user:
            raise ApiException(status.HTTP_404_NOT_FOUND, user_not_found_error)

        # Get namespace_id from the found namespace
        namespace_id = (
            namespace.get("id") if isinstance(namespace, dict) else namespace.id
        )

        # Get user's namespace_id
        user_namespace_id = (
            user.get("namespace_id") if isinstance(user, dict) else user.namespace_id
        )

        # Verify user belongs to the namespace
        if user_namespace_id != namespace_id:
            raise ApiException(
                status.HTTP_400_BAD_REQUEST, user_namespace_mismatch_error
            )

        return func(
            hotel_name, user_email, country, city, db, user=user, namespace=namespace
        )

    return wrapper


@check_account_data
def handle_approve_account(
    hotel_name: str,
    user_email: str,
    country: str,
    city: str,
    db,
    user=None,
    namespace=None,
):
    """
    Approve an account by sending verification email to the owner.

    Args:
        hotel_name: Hotel name
        user_email: User email address
        country: Country
        city: City
        db: Database session

    Returns:
        dict: Success message

    Raises:
        ApiException: If namespace or user not found, or user doesn't belong to namespace
    """

    # Get user's first name for email
    first_name = user.get("first_name") if isinstance(user, dict) else user.first_name

    # Prepare verification link
    verification_link = f"{str(settings.application_url) + settings.email_confirmation_router}{sign_jwt(user, expires=3600)}"

    # Send verification email
    send_email(user_email, first_name, verification_link)

    return {"data": "Owner notified by approval of his account"}


@check_account_data
def handle_reject_account(
    hotel_name: str,
    user_email: str,
    country: str,
    city: str,
    db,
    user=None,
    namespace=None,
):
    """
    Reject an account by sending rejection email and deleting the namespace.

    Args:
        hotel_name: Hotel name
        user_email: User email address
        country: Country
        city: City
        db: Database session

    Returns:
        dict: Success message

    Raises:
        ApiException: If namespace or user not found, or user doesn't belong to namespace
    """

    namespace_id = namespace.get("id") if isinstance(namespace, dict) else namespace.id

    # Send rejection email to the owner
    send_account_rejection_email(to_email=user_email, hotel_name=hotel_name)

    # Delete the namespace from the database
    namespace_controller.delete(namespace_id, db=db)

    return {"data": "Account removed successfully from the database"}
