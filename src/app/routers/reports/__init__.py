from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.app.db.orm import get_db
from src.app.globals.response import ApiResponse
from src.app.routers.reports.services import (
    get_namespaces_in_report_window,
    publish_report_jobs,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/daily-summary", response_model=ApiResponse)
def trigger_daily_summary(db: Session = Depends(get_db)):
    """Called by Cloud Scheduler to fan out daily performance report jobs.

    Publishes one DAILY_PERFORMANCE_REPORT Pub/Sub job for every namespace
    whose local time is currently between 09:00 and 09:59.
    """
    namespaces = get_namespaces_in_report_window(db)
    published = publish_report_jobs(namespaces)
    return ApiResponse(data={"published": published, "namespace_ids": [ns_id for ns_id, _ in namespaces]})
