from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from src.app.globals.schema_models import Role
from src.app.db.models.namespace_settings import NamespaceSettings
from fastapi import HTTPException
from src.app.routers.namespace_settings.modelsIn import SettingsCreate, SettingsUpdate
from src.app.resourcesController import settings_controller


def check_user_permissions(user: dict) -> None:
    """Check if user has required role"""
    allowed_roles = [Role.supervisor.value, Role.owner.value, Role.admin.value]
    if user["role"] not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors, owners, and admins can manage namespace settings",
        )


def check_namespace_settings_exist(namespace_id: int) -> None:
    """Check if settings already exist for the namespace"""
    existing_settings = settings_controller.find_by_field("namespace_id", namespace_id)
    if existing_settings:
        raise HTTPException(
            status_code=400,
            detail="Settings already exist for this namespace. Use update endpoint instead.",
        )


def check_settings_exist_by_id(settings_id: int) -> None:
    """Check if settings exist by ID"""
    existing_settings = settings_controller.find_by_id(settings_id)
    if not existing_settings:
        raise HTTPException(
            status_code=404,
            detail="Settings not found",
        )


def _calculate_default_times(settings: SettingsCreate) -> dict:
    """Calculate default values for optional time fields"""
    defaults = {}

    check_in_time = datetime.combine(datetime.today(), settings.check_in_time)
    dinner_end_time = datetime.combine(datetime.today(), settings.dinner_end_time)

    # restaurant_survey_time defaults to dinner_end_time
    if not settings.restaurant_survey_time and settings.dinner_end_time:
        defaults["restaurant_survey_time"] = settings.dinner_end_time

    # room_survey_time defaults to check_in_time + 2 hours
    if not settings.room_survey_time and settings.check_in_time:
        defaults["room_survey_time"] = (check_in_time + timedelta(hours=2)).time()

    # lunch_menu_time defaults to breakfast_end_time
    if not settings.lunch_menu_time and settings.breakfast_end_time:
        defaults["lunch_menu_time"] = settings.breakfast_end_time

    # dinner_menu_time defaults to lunch_end_time
    if not settings.dinner_menu_time and settings.lunch_end_time:
        defaults["dinner_menu_time"] = settings.lunch_end_time

    # breakfast_menu_time defaults to dinner_end_time + 1 hour
    if not settings.breakfast_menu_time and settings.dinner_end_time:
        defaults["breakfast_menu_time"] = (dinner_end_time + timedelta(hours=1)).time()

    return defaults


def create_settings(
    db: Session, namespace_id: int, settings: SettingsCreate
) -> NamespaceSettings:
    # Check if settings already exist
    check_namespace_settings_exist(namespace_id)

    # Calculate default values
    defaults = _calculate_default_times(settings)

    # Create settings with defaults
    db_settings = dict(
        namespace_id=namespace_id,
        breakfast_start_time=settings.breakfast_start_time,
        breakfast_end_time=settings.breakfast_end_time,
        lunch_start_time=settings.lunch_start_time,
        lunch_end_time=settings.lunch_end_time,
        dinner_start_time=settings.dinner_start_time,
        dinner_end_time=settings.dinner_end_time,
        restaurant_survey_time=settings.restaurant_survey_time
        or defaults.get("restaurant_survey_time"),
        room_survey_time=settings.room_survey_time or defaults.get("room_survey_time"),
        breakfast_menu_time=settings.breakfast_menu_time
        or defaults.get("breakfast_menu_time"),
        lunch_menu_time=settings.lunch_menu_time or defaults.get("lunch_menu_time"),
        dinner_menu_time=settings.dinner_menu_time or defaults.get("dinner_menu_time"),
        check_in_time=settings.check_in_time,
        check_out_time=settings.check_out_time,
    )
    new_settings = settings_controller.create(db_settings, db)
    return new_settings


def get_settings(namespace_id: int) -> dict:
    return settings_controller.find_by_field("namespace_id", namespace_id)


def update_settings(db: Session, settings_id: int, settings: SettingsUpdate) -> dict:
    # Check if settings exist before updating
    check_settings_exist_by_id(settings_id)

    new_settings = settings_controller.update(
        settings_id, settings.model_dump(exclude_unset=True), db=db
    )
    return new_settings
