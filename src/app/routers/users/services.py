from src.app.globals.schema_models import Role
from src.app.globals.exceptions import ApiException
from fastapi import status, HTTPException
from src.app.resourcesController import users_controller


def check_user_scope(user: dict, scopes: list[Role]):
    if user["role"] not in scopes:
        raise ApiException(
            status.HTTP_403_FORBIDDEN,
            "User does not have permission to access this resource",
        )


def check_user_exist(user_id: int):
    user = users_controller.find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
