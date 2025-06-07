from fastapi import FastAPI
from .auth import router as user_router
from .claims import router as claims_router
from .stays import router as stay_router
from .users import router as users_router
from .namespace_settings import router as namespace_settings_router
from .health_check import router as health_check_router


def add_routers(app: FastAPI):
    app.include_router(user_router)
    app.include_router(claims_router)
    app.include_router(stay_router)
    app.include_router(users_router)
    app.include_router(namespace_settings_router)
    app.include_router(health_check_router)
