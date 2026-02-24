from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from src.app.globals.schema_models import Role
from fastapi import HTTPException
from src.app.routers.namespace_settings.modelsIn import SettingsCreate, SettingsUpdate
from src.app.resourcesController import settings_controller


def check_user_permissions(user: dict) -> None:
    """Check if user has required role"""
    allowed_roles = {Role.supervisor.value, Role.owner.value, Role.admin.value}
    if not set(user.get("role", [])) & allowed_roles:
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
            detail="Settings already exist for this namespace.",
        )


def check_settings_exist_by_id(settings_id: int) -> None:
    """Check if settings exist by ID"""
    existing_settings = settings_controller.find_by_id(settings_id)
    if not existing_settings:
        raise HTTPException(
            status_code=404,
            detail="Settings not found",
        )


def _nested_to_flat(settings) -> dict:
    """Convert nested Pydantic model to flat dict matching DB columns."""
    flat = {}
    data = settings.model_dump(exclude_unset=True)

    if "restaurant_hours" in data:
        rh = data["restaurant_hours"]
        if "breakfast" in rh:
            flat["breakfast_start_time"] = rh["breakfast"]["start"]
            flat["breakfast_end_time"] = rh["breakfast"]["end"]
        if "lunch" in rh:
            flat["lunch_start_time"] = rh["lunch"]["start"]
            flat["lunch_end_time"] = rh["lunch"]["end"]
        if "dinner" in rh:
            flat["dinner_start_time"] = rh["dinner"]["start"]
            flat["dinner_end_time"] = rh["dinner"]["end"]

    if "menu_schedule" in data:
        ms = data["menu_schedule"]
        if "breakfast_time" in ms:
            flat["breakfast_menu_time"] = ms["breakfast_time"]
        if "lunch_time" in ms:
            flat["lunch_menu_time"] = ms["lunch_time"]
        if "dinner_time" in ms:
            flat["dinner_menu_time"] = ms["dinner_time"]

    if "surveys" in data and data["surveys"]:
        sv = data["surveys"]
        if "restaurant_time" in sv:
            flat["restaurant_survey_time"] = sv["restaurant_time"]
        if "room_time" in sv:
            flat["room_survey_time"] = sv["room_time"]

    if "check_in_out" in data:
        cio = data["check_in_out"]
        if "checkin_time" in cio:
            flat["check_in_time"] = cio["checkin_time"]
        if "checkout_time" in cio:
            flat["check_out_time"] = cio["checkout_time"]

    return flat


def _flat_to_nested(db_dict: dict) -> dict:
    """Convert flat DB dict to nested structure for SettingsResponse."""
    return {
        "id": db_dict.get("id"),
        "namespace_id": db_dict["namespace_id"],
        "restaurant_hours": {
            "breakfast": {
                "start": db_dict["breakfast_start_time"],
                "end": db_dict["breakfast_end_time"],
            },
            "lunch": {
                "start": db_dict["lunch_start_time"],
                "end": db_dict["lunch_end_time"],
            },
            "dinner": {
                "start": db_dict["dinner_start_time"],
                "end": db_dict["dinner_end_time"],
            },
        },
        "menu_schedule": {
            "breakfast_time": db_dict["breakfast_menu_time"],
            "lunch_time": db_dict["lunch_menu_time"],
            "dinner_time": db_dict["dinner_menu_time"],
        },
        "surveys": {
            "restaurant_time": db_dict["restaurant_survey_time"],
            "room_time": db_dict["room_survey_time"],
        },
        "check_in_out": {
            "checkin_time": db_dict["check_in_time"],
            "checkout_time": db_dict["check_out_time"],
        },
        "created_at": db_dict.get("created_at"),
        "updated_at": db_dict.get("updated_at"),
    }


def _calculate_default_times(settings: SettingsCreate) -> dict:
    """Calculate default values for optional time fields"""
    defaults = {}

    if not settings.surveys:
        # restaurant_survey_time defaults to dinner end time
        defaults["restaurant_survey_time"] = settings.restaurant_hours.dinner.end
        # room_survey_time defaults to checkin_time + 2 hours
        checkin_dt = datetime.combine(datetime.today(), settings.check_in_out.checkin_time)
        defaults["room_survey_time"] = (checkin_dt + timedelta(hours=2)).time()

    return defaults


def create_settings(
    db: Session, namespace_id: int, settings: SettingsCreate
) -> dict:
    check_namespace_settings_exist(namespace_id)

    # Calculate default values
    defaults = _calculate_default_times(settings)

    # Convert nested to flat
    flat = _nested_to_flat(settings)
    flat["namespace_id"] = namespace_id

    # Apply defaults for missing survey times
    if "restaurant_survey_time" not in flat:
        flat["restaurant_survey_time"] = defaults.get("restaurant_survey_time")
    if "room_survey_time" not in flat:
        flat["room_survey_time"] = defaults.get("room_survey_time")

    new_settings = settings_controller.create(flat, db)
    return _flat_to_nested(new_settings)


def get_settings(namespace_id: int) -> dict:
    result = settings_controller.find_by_field("namespace_id", namespace_id)
    if not result:
        return None
    return _flat_to_nested(result)


def update_settings(db: Session, settings_id: int, settings: SettingsUpdate) -> dict:
    check_settings_exist_by_id(settings_id)

    flat = _nested_to_flat(settings)
    if not flat:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = settings_controller.update(settings_id, flat, db=db)
    return _flat_to_nested(updated)
