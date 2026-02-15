from src.app.globals.response import ApiResponse
from src.app.globals.exceptions import ApiException
from src.app.db.orm import get_db
from fastapi import Depends, Request, status
from src.app.globals.error import not_authenticated, invalid_token, Error
from src.app.secrets.jwt import decode_jwt
from src.app.secrets.passwords import generate_password
from src.app.resourcesController import users_controller, namespace_controller
from src.app.globals.schema_models import Role
from src.app.routers.auth.modelsOut import no_domain_error
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Literal
from src.app.resourcesController import (
    users_controller,
    claim_controller,
    guest_controller,
)
from src.app.globals.decorators import transactional
from src.app.globals.emails import send_account_confirmation_email
import logging

logger = logging.getLogger(__name__)


class domain_auth:
    def __init__(self, db=Depends(get_db)):
        self.db = db

    async def __call__(self, request: Request, db=Depends(get_db)):

        try:
            heads = request.headers

            token = heads["token-registry"]

        except Exception:
            raise ApiException(status.HTTP_403_FORBIDDEN, not_authenticated)
        user_data = decode_jwt(token)
        current_user = users_controller.find_by_id(user_data["id"])
        if current_user:
            user_roles = (
                current_user.get("role", [])
                if isinstance(current_user, dict)
                else current_user.role
            )
            if Role.owner.value not in user_roles:
                raise ApiException(status.HTTP_417_EXPECTATION_FAILED, no_domain_error)

            # Generate password
            password = generate_password()
            plain_password = password["plain_password"]
            hashed_password = password["hashed_password"]

            # Get user details for email
            user_email = (
                current_user.get("user_email")
                if isinstance(current_user, dict)
                else current_user.user_email
            )
            phone_number = (
                current_user.get("phone_number")
                if isinstance(current_user, dict)
                else current_user.phone_number
            )

            # Get namespace details
            namespace = namespace_controller.find_by_id(user_data["namespace_id"])
            hotel_name = (
                namespace.get("hotel_name")
                if isinstance(namespace, dict)
                else namespace.hotel_name
            )

            try:
                # Update user password and confirm account
                users_controller.update(
                    user_data["id"],
                    {"hashed_password": hashed_password},
                    commit=False,
                    db=db,
                )
                namespace_controller.update(
                    user_data["namespace_id"],
                    {"confirmed_account": True},
                    commit=False,
                    db=db,
                )

                # Send account confirmation email with credentials
                send_account_confirmation_email(
                    to_email=user_email,
                    hotel_name=hotel_name,
                    username=phone_number,
                    password=plain_password,
                )

                # Commit the transaction
                db.commit()

                logger.info(
                    f"Account confirmed and email sent successfully to {user_email}"
                )

            except Exception as e:
                # Rollback on any error
                db.rollback()
                logger.error(
                    f"Failed to send account confirmation email to {user_email}: {str(e)}",
                    exc_info=True,
                )
                raise ApiException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    Error(
                        type="email_error",
                        message=f"Account confirmation failed: {str(e)}",
                    ),
                )

        else:
            raise ApiException(status.HTTP_401_UNAUTHORIZED, invalid_token)


class CurrentUserIdentifier(HTTPBearer):
    def __init__(
        self,
        db=Depends(get_db),
        who: Literal["user", "guest", "any"] = None,
        raise_error=True,
    ):
        super().__init__()
        self.db = db
        self.who = who
        self.raise_error = raise_error

    async def __call__(self, request: Request) -> dict:
        try:
            credentials: Optional[HTTPAuthorizationCredentials] = (
                await super().__call__(request)
            )

        except:
            raise ApiException(status.HTTP_403_FORBIDDEN, not_authenticated)
        exception = ApiException(status.HTTP_400_BAD_REQUEST, invalid_token)

        if credentials and credentials.scheme == "Bearer":
            decoded_data = decode_jwt(credentials.credentials)
            if self.who == "user":
                if "id" in decoded_data:
                    user = users_controller.find_by_id(decoded_data["id"])
                    if not user:
                        if self.raise_error:
                            raise ApiException(
                                status.HTTP_401_UNAUTHORIZED,
                                Error(type="auth", message="Employee Not Found"),
                            )
                        return None
                elif self.raise_error:
                    raise ApiException(status.HTTP_401_UNAUTHORIZED, invalid_token)

            if self.who == "guest":
                if "phone_number" in decoded_data:
                    guest = guest_controller.find_by_field(
                        "phone_number", decoded_data["phone_number"]
                    )
                    if not guest:
                        if self.raise_error:
                            raise ApiException(
                                status.HTTP_401_UNAUTHORIZED,
                                Error(type="auth", message="Guest Not Found"),
                            )
                        return None
                elif self.raise_error:
                    raise ApiException(status.HTTP_401_UNAUTHORIZED, invalid_token)

            if self.who == "any":
                current_user = None
                if "id" in decoded_data:

                    current_user = users_controller.find_by_id(decoded_data["id"])
                elif "phone_number" in decoded_data:
                    current_user = guest_controller.find_by_field(
                        "phone_number", decoded_data["phone_number"]
                    )
                if current_user is None:
                    if self.raise_error:
                        raise ApiException(status.HTTP_401_UNAUTHORIZED, invalid_token)
                    return None

            return decoded_data
        raise exception
