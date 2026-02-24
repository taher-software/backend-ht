from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from psycopg2 import IntegrityError
from src.app.db.orm import get_db
from src.app.db.models.users import Users
from typing import Optional, List
from src.app.globals.schema_models import Role
from src.app.routers.users.modelsOut import (
    UserCreateResponse,
    UserResponse,
    AddRoleResponse,
    RemoveRoleResponse,
)
from src.app.routers.users.modelsIn import (
    UserCreate,
    UserUpdate,
    AddRoleRequest,
    RemoveRoleRequest,
    UserBase,
)
from sqlalchemy.orm import Session
from src.app.resourcesController import users_controller
from src.app.secrets.passwords import hash_password
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.routers.users.services import (
    check_user_scope,
    check_user_exist,
    add_role_to_user,
    remove_role_from_user,
    upload_user_avatar,
    delete_users,
)
from fastapi import Query
from src.app.globals.schema_models import Role
from pydantic import BaseModel
from src.app.globals.generic_responses import validation_response

router = APIRouter(prefix="/users", tags=["users"], responses={**validation_response})


@router.post("/", response_model=UserResponse)
def create_user(
    user: UserBase,
    avatar: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    db_user = {**user.dict(exclude={"password"})}
    db_user["namespace_id"] = current_user["namespace_id"]
    if avatar:
        db_user["avatar_url"] = upload_user_avatar(avatar)
    try:
        user_created = users_controller.create(db_user, db=db)
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this phone number already exists.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return UserResponse(**user_created)


@router.get("/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    check_user_exist(user_id)
    user = users_controller.find_by_id(user_id)
    return ApiResponse(data=UserResponse(**user).model_dump())


@router.get("/", response_model=ApiResponse)
def get_all_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(
        current_user, [Role.admin.value, Role.owner.value, Role.supervisor.value]
    )
    users = users_controller.get_all(namespace_id=current_user["namespace_id"])
    return ApiResponse(data=[UserResponse(**user) for user in users["items"]])


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserUpdate,
    avatar: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(
        current_user, [Role.admin.value, Role.owner.value, Role.supervisor.value]
    )
    check_user_exist(user_id)
    # Only include fields that were actually provided
    update_data = user.dict(exclude_unset=True, exclude={"password"})

    # Handle password separately if it was provided
    if user.password:
        update_data["hashed_password"] = hash_password(user.password)

    if avatar:
        update_data["avatar_url"] = upload_user_avatar(avatar)

    updated_user = users_controller.update(user_id, update_data, db=db)
    return UserResponse(**updated_user)


@router.delete("/", response_model=ApiResponse)
def delete_user(
    user_ids: list[int] = Query(..., description="List of user IDs to delete"),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    """Delete a list of users by their IDs."""
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    deleted_count = delete_users(user_ids=user_ids)

    return ApiResponse(data={"deleted_count": deleted_count})


@router.patch("/me/add-role", response_model=AddRoleResponse)
def add_role_to_current_user(
    request: AddRoleRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """
    Add a new role to the current authenticated user's role list.

    - **role**: Role to add (must be from Role enum)

    Returns the updated user data.
    """
    updated_user = add_role_to_user(current_user["id"], request.role, db)

    return AddRoleResponse(data=UserResponse(**updated_user))


@router.patch("/me/remove-role", response_model=RemoveRoleResponse)
def remove_role_from_current_user(
    request: RemoveRoleRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    """
    Remove a role from the current authenticated user's role list.

    - **role**: Role to remove (must be from Role enum)

    Returns the updated user data.
    Note: Cannot remove the last role from a user.
    """
    updated_user = remove_role_from_user(current_user["id"], request.role, db)

    return RemoveRoleResponse(data=UserResponse(**updated_user))
