from src.app.globals.schema_models import Role
from src.app.globals.exceptions import ApiException
from src.app.globals.decorators import transactional
from fastapi import status, HTTPException, UploadFile
from src.app.resourcesController import users_controller
from src.app.gcp.gcs import storage_client
from sqlalchemy.orm import Session
import tempfile
import os


def check_user_scope(user: dict, scopes: list[Role]):
    roles = user.get("role", [])

    if not any(role in scopes for role in roles):
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


def add_role_to_user(user_id: int, new_role: Role, db: Session) -> dict:
    """
    Adds a new role to user's role list if not already present.

    Args:
        user_id: User's ID
        new_role: Role to add
        db: Database session

    Returns:
        Updated user dictionary

    Raises:
        HTTPException: If user not found or role already exists
    """
    user = users_controller.find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    current_roles = user.get("role", [])
    if new_role.value in current_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User already has role: {new_role.value}",
        )

    updated_roles = current_roles + [new_role.value]

    updated_user = users_controller.update(user_id, {"role": updated_roles}, db=db)

    return updated_user


def remove_role_from_user(user_id: int, role_to_remove: Role, db: Session) -> dict:
    """
    Removes a role from user's role list if present.

    Args:
        user_id: User's ID
        role_to_remove: Role to remove
        db: Database session

    Returns:
        Updated user dictionary

    Raises:
        HTTPException: If user not found, role doesn't exist, or trying to remove last role
    """
    user = users_controller.find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    current_roles = user.get("role", [])
    if role_to_remove.value not in current_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User does not have role: {role_to_remove.value}",
        )

    updated_roles = [role for role in current_roles if role != role_to_remove.value]

    updated_user = users_controller.update(user_id, {"role": updated_roles}, db=db)

    return updated_user


@transactional
def delete_users(user_ids: list[int], db=None):
    for user_id in user_ids:
        user = users_controller.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )
        users_controller.delete(user_id, commit=False, db=db)

    return len(user_ids)


def upload_user_avatar(avatar: UploadFile) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        des_file = os.path.join(temp_dir, avatar.filename)
        with open(des_file, "wb") as f:
            f.write(avatar.file.read())
        avatar_url = storage_client.upload_to_bucket(
            "profiles_avatars", des_file, avatar.filename
        )
    return avatar_url
