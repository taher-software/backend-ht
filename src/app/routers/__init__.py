from fastapi import FastAPI
from .auth import router as user_router
from .claims import router as claims_router


def add_routers(app: FastAPI):
    app.include_router(user_router)
    app.include_router(claims_router)
