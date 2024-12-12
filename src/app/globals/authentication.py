from src.app.globals.response import ApiResponse
from src.app.globals.exceptions import ApiException
from src.app.db.orm import get_db
from fastapi import Depends, Request, status
from src.app.globals.error import not_authenticated, invalid_token
from src.app.secrets.jwt import decode_jwt
from src.app.resourcesController import users_controller, namespace_controller
from src.app.globals.schema_models import Role
from src.app.routers.auth.modelsOut import no_domain_error
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional


class domain_auth:
    def __init__(self, db=Depends(get_db)):
        self.db = db

    async def __call__(self, request: Request):

        try:
            heads = request.headers

            token = heads["token-registry"]

        except Exception:
            raise ApiException(status.HTTP_403_FORBIDDEN, not_authenticated)
        user_data = decode_jwt(token)
        current_user = users_controller.find_by_id(user_data["id"])
        if current_user:
            if current_user.role != Role.owner:
                raise ApiException(status.HTTP_417_EXPECTATION_FAILED, no_domain_error)
            namespace_controller.update(
                user_data["namespace_id"], {"confirmed_account": True}
            )
        else:
            raise ApiException(status.HTTP_401_UNAUTHORIZED, invalid_token)


class CurrentUserIdentifier(HTTPBearer):
    def __init__(self, db=Depends(get_db)):
        super().__init__()
        self.db = db

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

            return decoded_data
        raise exception
