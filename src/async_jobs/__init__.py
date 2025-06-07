from celery import Celery
from src.settings import settings

celery_app = Celery(
    "bodor_celery",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
)

celery_app.autodiscover_tasks(["src.async_jobs.tasks", "src.async_jobs.periodic_tasks"])
