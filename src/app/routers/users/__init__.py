from fastapi import APIRouter, Depends, HTTPException
from src.app.db.orm import get_db
from src.app.db.models.users import Users
from typing import Optional, List
from src.app.globals.schema_models import Role
from src.app.routers.users.modelsOut import UserCreateResponse, UserResponse
from src.app.routers.users.modelsIn import UserCreate, UserUpdate
from sqlalchemy.orm import Session
from src.app.resourcesController import users_controller
from src.app.secrets.passwords import hash_password
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.routers.users.services import check_user_scope, check_user_exist
from src.app.globals.schema_models import Role
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    db_user = {**user.dict(exclude={"password"})}
    db_user["hashed_password"] = hash_password(user.password)
    db_user["namespace_id"] = current_user["namespace_id"]
    user_created = users_controller.create(db_user)

    return UserResponse(**user_created)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    check_user_exist(user_id)
    user = users_controller.find_by_id(user_id)
    return UserResponse(**user)


@router.get("/", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    users = users_controller.get_all(namespace_id=current_user["namespace_id"])
    return [UserResponse(**user) for user in users]


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    check_user_exist(user_id)
    # Only include fields that were actually provided
    update_data = user.dict(exclude_unset=True, exclude={"password"})

    # Handle password separately if it was provided
    if user.password:
        update_data["hashed_password"] = hash_password(user.password)

    updated_user = users_controller.update(user_id, update_data)
    return UserResponse(**updated_user)


@router.delete("/{user_id}", response_model=dict)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
):
    check_user_scope(current_user, [Role.admin.value, Role.owner.value])
    check_user_exist(user_id)
    deleted = users_controller.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}
