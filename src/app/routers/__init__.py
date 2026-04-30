from fastapi import FastAPI
from .auth import router as user_router
from .claims import router as claims_router
from .stays import router as stay_router
from .users import router as users_router
from .namespace_settings import router as namespace_settings_router
from .health_check import router as health_check_router
from .surveys import router as surveys_router
from .dishes import router as dishes_router
from .meals import router as meals_router
from .menu import router as menu_router
from .preferences import router as preferences_router
from .rooms import router as rooms_router
from .worker import router as worker_router
from .super_admin import router as super_admin_router
from .chat import router as chat_router
from .websocket import router as websocket_router
from .websocket import guest_connections, user_connections
from .guests import router as guests_router
from .housekeepers import router as housekeepers_router
from .assignments import router as assignments_router
from .stats import router as stats_router
from .reports import router as reports_router


def add_routers(app: FastAPI):
    app.include_router(user_router)
    app.include_router(claims_router)
    app.include_router(stay_router)
    app.include_router(users_router)
    app.include_router(namespace_settings_router)
    app.include_router(health_check_router)
    app.include_router(surveys_router)
    app.include_router(dishes_router)
    app.include_router(meals_router)
    app.include_router(menu_router)
    app.include_router(preferences_router)
    app.include_router(rooms_router)
    app.include_router(worker_router)
    app.include_router(super_admin_router)
    app.include_router(chat_router)
    app.include_router(websocket_router)
    app.include_router(guests_router)
    app.include_router(housekeepers_router)
    app.include_router(assignments_router)
    app.include_router(stats_router)
    app.include_router(reports_router)
