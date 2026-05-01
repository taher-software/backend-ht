from src.app.db.models.stays import Stay
from src.app.db.models.namespace_settings import NamespaceSettings
from src.app.db.models.namespace import Namespace
from src.app.db.models.meals import Meal
from src.app.db.models.menu import Menu
from src.app.db.models.dishes import Dishes
from src.app.globals.enum import MealEnum
from datetime import datetime, timezone as stdlib_timezone
from pytz import timezone, UTC
from fastapi import HTTPException
from src.app.globals.utils import (
    breakfast_eligible_plans,
    lunch_eligible_plans,
    dinner_eligible_plans,
)
from src.settings import client
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# Service logic for menu endpoints will go here


def get_current_menu(db, current_guest):
    utc_today = datetime.now(UTC).date()
    # Get current stay
    current_stay = (
        db.query(Stay)
        .filter(
            Stay.guest_id == current_guest["phone_number"],
            Stay.start_date <= utc_today,
            Stay.end_date >= utc_today,
        )
        .first()
    )
    if not current_stay:
        raise HTTPException(
            status_code=404, detail="No active stay found for this guest"
        )
    namespace_id = current_stay.namespace_id
    # Get namespace settings
    ns_settings = (
        db.query(NamespaceSettings)
        .filter(NamespaceSettings.namespace_id == namespace_id)
        .first()
    )
    if not ns_settings:
        raise HTTPException(status_code=404, detail="Namespace settings not found")
    namespace = db.query(Namespace).filter(Namespace.id == namespace_id).first()
    namespace_tz = timezone(namespace.timezone)
    now_local = datetime.now(UTC).astimezone(namespace_tz)
    now = now_local.time()
    today = now_local.date()

    # Determine eligible meals by meal plan
    plan = current_stay.meal_plan
    breakfast_eligible = plan in breakfast_eligible_plans
    lunch_eligible = plan in lunch_eligible_plans
    dinner_eligible = plan in dinner_eligible_plans
    meal_type = None
    # Check breakfast
    if (
        breakfast_eligible
        and ns_settings.breakfast_menu_time <= now <= ns_settings.breakfast_end_time
    ):
        meal_type = MealEnum.BREAKFAST
    # Check lunch
    if (
        lunch_eligible
        and ns_settings.lunch_menu_time <= now <= ns_settings.lunch_end_time
    ):
        meal_type = MealEnum.LUNCH
    # Check dinner
    if (
        dinner_eligible
        and ns_settings.dinner_menu_time <= now <= ns_settings.dinner_end_time
    ):
        meal_type = MealEnum.DINNER
    if not meal_type:
        return dict(meal_type=None, menu=[], meal_time_range=None)
    meal = (
        db.query(Meal)
        .filter(
            Meal.namespace_id == namespace_id,
            Meal.meal_type == meal_type.value,
            Meal.meal_date == today,
        )
        .first()
    )
    result = []
    if meal:
        menu_entries = db.query(Menu).filter(Menu.meal_id == meal.id).all()
        dish_ids = [entry.dishes_id for entry in menu_entries]
        dishes = db.query(Dishes).filter(Dishes.id.in_(dish_ids)).all()
        guest_pref_lang = current_guest.get("pref_language", None)
        for dish in dishes:
            result.append(
                {
                    "id": dish.id,
                    "name": dish.name,
                    "description": (
                        translate_description(guest_pref_lang, dish.description)
                        if guest_pref_lang
                        else dish.description
                    ),
                    "img_url": dish.img_url,
                }
            )
    meal_time_range = format_meal_time_range(ns_settings, meal_type)
    response = dict(
        meal_type=meal_type.value, menu=result, meal_time_range=meal_time_range
    )

    return response


def format_meal_time_range(ns_settings, meal_type: MealEnum):
    def format_time(t):
        return t.strftime("%-I:%M %p") if t else ""

    if meal_type == MealEnum.BREAKFAST:
        return f"{format_time(ns_settings.breakfast_menu_time)} - {format_time(ns_settings.breakfast_end_time)}"
    elif meal_type == MealEnum.LUNCH:
        return f"{format_time(ns_settings.lunch_menu_time)} - {format_time(ns_settings.lunch_end_time)}"
    elif meal_type == MealEnum.DINNER:
        return f"{format_time(ns_settings.dinner_menu_time)} - {format_time(ns_settings.dinner_end_time)}"
    return ""


@lru_cache()
def translate_description(target_language: str, description: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are an AI translation assistant. Your task is to translate a given description accurately  to the {target_language}. Follow these guidelines:
                              - Keep the original meaning and tone of the text intact.
                              - If there are idioms or expressions, translate them into equivalent expressions in the target language where possible.
                              - Avoid translating proper names, brand names, or technical terms unless they have standard equivalents in the target language.
                              - Return only the translated text with no additional information or explanations.""",
            },
            {"role": "user", "content": description},
        ],
    )
    return completion.choices[0].message.content
