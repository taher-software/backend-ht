from src.app.globals.response import ApiResponse
from src.app.routers.users.modelsIn import UserBase


class UserResponse(UserBase):
    id: int | None = None
    namespace_id: int

    class Config:
        from_attributes = True


class UserCreateResponse(ApiResponse):
    data: UserResponse


class AddRoleResponse(ApiResponse):
    data: UserResponse


class RemoveRoleResponse(ApiResponse):
    data: UserResponse
