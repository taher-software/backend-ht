from src.app.globals.utils import (
    room_guest_satis_questions,
    room_reception_questions,
    restaurant_exp_questions,
    queue_factors,
    dishes_questions,
)
from src.settings import client
import backoff
import openai
import ast
import json
import logging
from typing import List

logger = logging.getLogger(__name__)
from datetime import datetime, date
from pytz import timezone, UTC
from sqlalchemy import and_, distinct
from src.app.db.models.namespace_settings import NamespaceSettings
from src.app.db.models import Namespace
from src.app.db.models import DailyRestaurantSurvey
from src.app.db.models import RoomReceptionSurvey
from src.app.db.models import DailyRoomSatisfactionSurvey
from src.app.db.models.queue_root_cause import QueueRootCause
from src.app.db.models import Stay
from src.app.globals.enum import Survey
from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.app.globals.utils import queue_factors
from src.app.db.models.stays import Stay
from src.app.db.models.room_reception_survey import RoomReceptionSurvey
from src.app.db.models.daily_restaurant_survey import DailyRestaurantSurvey
from src.app.db.models.daily_room_sat_survey import DailyRoomSatisfactionSurvey
from src.app.resourcesController import (
    room_reception_survey_controller,
    daily_restaurant_survey_controller,
    daily_room_satisfaction_survey_controller,
    queue_root_cause_controller,
)
from src.app.globals.decorators import transactional
from src.app.gcp import firestore_client
from src.app.globals.response import ApiResponse
from src.app.globals.utils import dishes_questions
from src.app.db.models.dishes import Dishes
from src.app.db.models.meals import Meal
from src.app.db.models.menu import Menu
from src.app.globals.enum import MealEnum, CachingCollectionName
from src.app.db.models.dishes_survey import DishesSurvey
from src.app.db.models.housekeeper_assignment import HousekeeperAssignment
from .modelsIn import DishesSurveySubmitPayload
from src.app.globals.satisfaction import check_and_trigger_satisfaction_alert
from src.app.resourcesController import settings_controller

questions_labels = {
    "daily_room": room_guest_satis_questions,
    "room_reception": room_reception_questions,
    "restaurant_exp": restaurant_exp_questions,
    "queue_factors": queue_factors,
    "dishes": dishes_questions,
}


def get_all_active_namespaces(db: Session) -> List[int]:
    """
    Get all namespace IDs that currently have active guests.

    Returns namespaces where there are stays with:
    - start_date < today < end_date

    Args:
        db: Database session

    Returns:
        List of namespace IDs with active guests
    """
    try:
        today = datetime.today().date()

        # Query distinct namespace_ids from Stay table where guests are currently active
        namespace_ids = (
            db.query(distinct(Stay.namespace_id))
            .filter(Stay.start_date < today, Stay.end_date > today)
            .all()
        )

        # Extract namespace_id from tuples
        result = [ns_id[0] for ns_id in namespace_ids]

        logger.info(f"Found {len(result)} namespaces with active guests: {result}")
        return result

    except Exception as e:
        logger.error(f"Error getting active namespaces: {str(e)}", exc_info=True)
        raise


def get_current_stay(db: Session, phone_number: str) -> Stay:
    """Get the current stay for a guest"""
    today = date.today()
    current_stay = (
        db.query(Stay)
        .filter(
            and_(
                Stay.guest_id == phone_number,
                Stay.start_date <= today,
                Stay.end_date >= today,
            )
        )
        .first()
    )
    if not current_stay:
        raise HTTPException(
            status_code=404,
            detail="No active stay found for this guest",
        )
    return current_stay


_SURVEY_TRANSLATION_COLLECTIONS = {
    "daily_room": CachingCollectionName.SURVEY_TRANSLATIONS_DAILY_ROOM,
    "room_reception": CachingCollectionName.SURVEY_TRANSLATIONS_ROOM_RECEPTION,
    "restaurant_exp": CachingCollectionName.SURVEY_TRANSLATIONS_RESTAURANT_EXP,
    "queue_factors": CachingCollectionName.SURVEY_TRANSLATIONS_QUEUE_FACTORS,
    "dishes": CachingCollectionName.SURVEY_TRANSLATIONS_DISHES,
}


@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3)
def translate_list_of_data(language: str, data_label: str) -> list[str] | str:
    data = questions_labels.get(data_label)
    if not data:
        return f"Error: Unknown data label '{data_label}'"

    lang_key = language.lower()
    collection = _SURVEY_TRANSLATION_COLLECTIONS.get(data_label)

    if collection:
        cached = firestore_client.get_document(collection_name=collection, document_id=lang_key)
        if cached and "translations" in cached:
            return cached["translations"]

    prompt = (
        f"The target language is {language}. "
        f"Translate the following list of strings into the target language, while keeping the structure exactly the same. "
        f"Respond ONLY with a valid JSON array of strings (no explanation):\n\n{data}"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI translator. "
                        "Given a list of questions or labels, you will translate them into the specified language. "
                        "Respond only with a valid JSON array. Use proper JSON escaping for special characters."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw_output = completion.choices[0].message.content.strip()
        if raw_output.startswith("```"):
            raw_output = raw_output.split("\n", 1)[1]
            raw_output = raw_output.rsplit("```", 1)[0]
            raw_output = raw_output.strip()
        translations = json.loads(raw_output)
        if collection:
            firestore_client.create_document(
                collection_name=collection,
                data={"translations": translations},
                document_id=lang_key,
            )
        return translations
    except Exception as e:
        logger.error(f"Translation error for {data_label}: {e}")
        raise e


@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3)
def translate_queue_factors(language: str) -> list[str] | str:
    lang_key = language.lower()
    collection = CachingCollectionName.SURVEY_TRANSLATIONS_QUEUE_FACTORS

    cached = firestore_client.get_document(collection_name=collection, document_id=lang_key)
    if cached and "translations" in cached:
        return cached["translations"]

    prompt = (
        f"The target language is {language}. "
        f"Translate the following list of strings into the target language, while keeping the structure exactly the same. "
        f"Respond ONLY with a valid JSON array of strings (no explanation):\n\n{queue_factors}"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI translator. "
                        "Given a list of questions or labels, you will translate them into the specified language. "
                        "Respond only with a valid JSON array. Use proper JSON escaping for special characters."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw_output = completion.choices[0].message.content.strip()
        if raw_output.startswith("```"):
            raw_output = raw_output.split("\n", 1)[1]
            raw_output = raw_output.rsplit("```", 1)[0]
            raw_output = raw_output.strip()
        translations = json.loads(raw_output)
        firestore_client.create_document(
            collection_name=collection,
            data={"translations": translations},
            document_id=lang_key,
        )
        return translations
    except Exception as e:
        logger.error(f"Translation error for queue_factors: {e}")
        raise e


@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3)
def translate_dishes_meal_template(language: str) -> str:
    lang_key = language.lower()
    collection = CachingCollectionName.SURVEY_TRANSLATIONS_DISHES_MEAL_TEMPLATE

    cached = firestore_client.get_document(collection_name=collection, document_id=lang_key)
    if cached and "template" in cached:
        return cached["template"]

    source = dishes_questions[0]
    prompt = (
        f"The target language is {language}. "
        f"Translate the following string accurately. "
        f"It contains a Python positional placeholder {{}} that must be kept exactly as-is in the translation. "
        f"Respond with only the translated string, nothing else:\n\n{source}"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI translator. "
                        "Translate the given string into the target language. "
                        "Preserve any {} placeholders exactly as they appear in the original."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        template = completion.choices[0].message.content.strip()
        firestore_client.create_document(
            collection_name=collection,
            data={"template": template},
            document_id=lang_key,
        )
        return template
    except Exception as e:
        logger.error(f"Translation error for dishes meal template: {e}")
        raise e


@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3)
def translate_meal_tast_question(language: str, question: str) -> str:
    lang_key = f"{language.lower()}_{question}"
    collection = CachingCollectionName.SURVEY_TRANSLATIONS_MEAL_TAST_QUESTION

    cached = firestore_client.get_document(collection_name=collection, document_id=lang_key)
    if cached and "translation" in cached:
        return cached["translation"]

    prompt = (
        f"The target language is {language}. "
        f"Translate the following phrase or question accurately, preserving its intended meaning:\n\n{question}"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI translator. Translate the given phrase or question into the specified language."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        translation = completion.choices[0].message.content.strip()
        firestore_client.create_document(
            collection_name=collection,
            data={"translation": translation},
            document_id=lang_key,
        )
        return translation
    except Exception as e:
        logger.error(f"Translation error for meal tast question: {e}")
        raise e


def get_prioritized_survey(db: Session, current_user: dict) -> dict:
    """Get the prioritized survey based on user's stay and time"""
    # Get current stay
    current_stay = get_current_stay(db, current_user["phone_number"])
    namespace_id = current_stay.namespace_id

    # Get namespace settings
    namespace_settings = (
        db.query(NamespaceSettings)
        .filter(NamespaceSettings.namespace_id == namespace_id)
        .first()
    )
    if not namespace_settings:
        raise HTTPException(status_code=404, detail="Namespace settings not found")

    # Get current time in namespace's timezone
    namespace = db.query(Namespace).filter(Namespace.id == namespace_id).first()
    namespace_tz = timezone(namespace.timezone)
    current_time = datetime.now(UTC).astimezone(namespace_tz).time()
    today = date.today()

    # Check restaurant survey first
    if current_time >= namespace_settings.restaurant_survey_time:
        # Determine allowed meals from current_stay.meal_plan
        allowed_meals = []
        if hasattr(current_stay, "meal_plan"):
            plan = current_stay.meal_plan
            # Map meal plan to allowed meals
            if plan in ["BB", "HB", "FB", "AIS", "AI"]:
                allowed_meals.append("breakfast")
            if plan in ["HB", "FB", "AIS", "AI"]:
                allowed_meals.append("lunch")
            if plan in ["FB", "AIS", "AI"]:
                allowed_meals.append("dinner")

        if len(allowed_meals) > 0:

            # Check if restaurant survey already exists for today
            existing_restaurant_survey = (
                db.query(DailyRestaurantSurvey)
                .filter(
                    and_(
                        DailyRestaurantSurvey.namespace_id == namespace_id,
                        DailyRestaurantSurvey.guest_phone_number
                        == current_user["phone_number"],
                        DailyRestaurantSurvey.created_at
                        >= datetime.combine(today, datetime.min.time()),
                        DailyRestaurantSurvey.created_at
                        < datetime.combine(today, datetime.max.time()),
                    )
                )
                .first()
            )
            if not existing_restaurant_survey:
                questions = (
                    translate_list_of_data(
                        current_user["pref_language"], "restaurant_exp"
                    )
                    if current_user["pref_language"]
                    else questions_labels["restaurant_exp"]
                )
                # Compose meal context questions

                meal_types = ["breakfast", "lunch", "dinner"]
                meal_questions = {}
                if current_user["pref_language"]:
                    meal_template = translate_dishes_meal_template(current_user["pref_language"])
                else:
                    meal_template = dishes_questions[0]
                for meal in meal_types:
                    meal_questions[f"{meal}_questions"] = meal_template.format(meal)
                # Add dish question (second item)
                raw_dish_q = dishes_questions[1]
                if current_user["pref_language"]:
                    dish_question = translate_meal_tast_question(
                        current_user["pref_language"], raw_dish_q
                    )
                else:
                    dish_question = raw_dish_q
                # Add breakfast/lunch/dinner dishes if allowed by stay meal plan
                breakfast_dishes = None
                lunch_dishes = None
                dinner_dishes = None

                # Use list_namespace_main_dishes to get dishes for each allowed meal
                if "breakfast" in allowed_meals:
                    breakfast_dishes = list_namespace_main_dishes(
                        namespace_id, MealEnum.BREAKFAST, db
                    )
                if "lunch" in allowed_meals:
                    lunch_dishes = list_namespace_main_dishes(
                        namespace_id, MealEnum.LUNCH, db
                    )
                if "dinner" in allowed_meals:
                    dinner_dishes = list_namespace_main_dishes(
                        namespace_id, MealEnum.DINNER, db
                    )
                return {
                    "survey_type": Survey.RESTAURANT,
                    "survey_questions": questions,
                    "queue_factors": (
                        translate_queue_factors(current_user["pref_language"])
                        if current_user["pref_language"]
                        else queue_factors
                    ),
                    **meal_questions,
                    "dish_question": dish_question,
                    "breakfast_dishes": breakfast_dishes,
                    "lunch_dishes": lunch_dishes,
                    "dinner_dishes": dinner_dishes,
                }

    # Check guest stay dates
    if current_stay.start_date == today:
        # Check room reception survey
        existing_reception_survey = (
            db.query(RoomReceptionSurvey)
            .filter(
                and_(
                    RoomReceptionSurvey.namespace_id == namespace_id,
                    RoomReceptionSurvey.guest_phone_number
                    == current_user["phone_number"],
                    RoomReceptionSurvey.created_at
                    >= datetime.combine(today, datetime.min.time()),
                    RoomReceptionSurvey.created_at
                    < datetime.combine(today, datetime.max.time()),
                )
            )
            .first()
        )
        if not existing_reception_survey:
            questions = (
                translate_list_of_data(current_user["pref_language"], "room_reception")
                if current_user["pref_language"]
                else questions_labels["room_reception"]
            )
            return {"survey_type": Survey.ROOM_RECEPTION, "survey_questions": questions}
    elif today < current_stay.end_date:
        # Check daily room satisfaction survey
        if current_time >= namespace_settings.room_survey_time:
            existing_room_survey = (
                db.query(DailyRoomSatisfactionSurvey)
                .filter(
                    and_(
                        DailyRoomSatisfactionSurvey.namespace_id == namespace_id,
                        DailyRoomSatisfactionSurvey.guest_phone_number
                        == current_user["phone_number"],
                        DailyRoomSatisfactionSurvey.created_at
                        >= datetime.combine(today, datetime.min.time()),
                        DailyRoomSatisfactionSurvey.created_at
                        < datetime.combine(today, datetime.max.time()),
                    )
                )
                .first()
            )
            if not existing_room_survey:
                questions = (
                    translate_list_of_data(current_user["pref_language"], "daily_room")
                    if current_user["pref_language"]
                    else questions_labels["daily_room"]
                )
                return {
                    "survey_type": Survey.DAILY_ROOM,
                    "survey_questions": questions,
                }

    return None  # No survey needed at this time


@transactional
def submit_survey(payload, current_guest, db: Session):
    """
    Handles survey submission for ROOM_RECEPTION, RESTAURANT, and DAILY_ROOM types.
    """
    # Extract current stay
    phone_number = current_guest["phone_number"]
    today = date.today()
    current_stay = (
        db.query(Stay)
        .filter(
            Stay.guest_id == phone_number,
            Stay.start_date <= today,
            Stay.end_date >= today,
        )
        .first()
    )
    if not current_stay:
        raise HTTPException(
            status_code=404, detail="No active stay found for this guest"
        )

    namespace_id = current_stay.namespace_id
    room_id = current_stay.room_id
    responses = payload.responses
    survey_type = payload.survey_type
    stay_id = current_stay.id

    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    survey_model_map = {
        Survey.ROOM_RECEPTION: RoomReceptionSurvey,
        Survey.RESTAURANT: DailyRestaurantSurvey,
        Survey.DAILY_ROOM: DailyRoomSatisfactionSurvey,
    }
    duplicate = None
    survey_model = survey_model_map.get(survey_type)
    if survey_model:
        duplicate = (
            db.query(survey_model)
            .filter(
                survey_model.namespace_id == namespace_id,
                survey_model.guest_phone_number == phone_number,
                survey_model.stay_id == stay_id,
                survey_model.created_at >= today_start,
                survey_model.created_at < today_end,
            )
            .first()
        )
    if duplicate:
        raise HTTPException(
            status_code=429,
            detail="Survey already submitted for today.",
        )

    # Validate responses
    if survey_type == Survey.RESTAURANT:
        # All except 4th and 5th item
        for i, val in enumerate(responses):
            if i == 3:
                if val not in [0, 1]:
                    raise HTTPException(
                        status_code=400,
                        detail="Fourth response must be 0 or 1 for RESTAURANT survey.",
                    )
            elif i == 4:
                if val not in [1, 2, 3]:
                    raise HTTPException(
                        status_code=400,
                        detail="Fifth response must be between 1 and 3 for RESTAURANT survey.",
                    )
            else:
                if val < 1 or val > 5:
                    raise HTTPException(
                        status_code=400,
                        detail="All responses (except 4th and 5th) must be between 1 and 5.",
                    )
    else:
        for val in responses:
            if val < 1 or val > 5:
                raise HTTPException(
                    status_code=400, detail="All responses must be between 1 and 5."
                )

    # Control number of items in responses
    if survey_type == Survey.RESTAURANT:
        if len(responses) not in [4, 5]:
            raise HTTPException(
                status_code=400,
                detail="For RESTAURANT survey, responses must have 4 or 5 items.",
            )
    else:
        if len(responses) != 4:
            raise HTTPException(
                status_code=400, detail="Responses must have exactly 4 items."
            )

    survey_data = dict(
        namespace_id=namespace_id,
        guest_phone_number=phone_number,
        stay_id=stay_id,
        Q1=responses[0] if len(responses) > 0 else None,
        Q2=responses[1] if len(responses) > 1 else None,
        Q3=responses[2] if len(responses) > 2 else None,
        Q4=responses[3] if len(responses) > 3 else None,
    )
    if survey_type == Survey.ROOM_RECEPTION:
        survey_data["room_id"] = room_id
        room_reception_survey_controller.create(survey_data, db, commit=False)
    elif survey_type == Survey.RESTAURANT:
        daily_restaurant_survey_controller.create(survey_data, db, commit=False)
        if len(responses) == 5:
            last_item = responses[4]
            queue_duplicate = (
                db.query(QueueRootCause)
                .filter(
                    QueueRootCause.namespace_id == namespace_id,
                    QueueRootCause.guest_phone_number == phone_number,
                    QueueRootCause.created_at >= today_start,
                    QueueRootCause.created_at < today_end,
                )
                .first()
            )
            if queue_duplicate:
                raise HTTPException(
                    status_code=429,
                    detail="Queue root cause already submitted for today.",
                )
            queue_data = dict(
                namespace_id=namespace_id,
                guest_phone_number=phone_number,
                r1=bool(last_item == 1),
                r2=bool(last_item == 2),
                r3=bool(last_item == 3),
            )
            queue_root_cause_controller.create(queue_data, db, commit=False)
    elif survey_type == Survey.DAILY_ROOM:
        assignment = (
            db.query(HousekeeperAssignment)
            .filter(
                HousekeeperAssignment.room_id == room_id,
                HousekeeperAssignment.date == today,
            )
            .first()
        )
        survey_data["housekeeper_id"] = assignment.housekeeper_id if assignment else None
        survey_data["room_id"] = room_id
        daily_room_satisfaction_survey_controller.create(survey_data, db, commit=False)
    else:
        raise HTTPException(status_code=400, detail="Invalid survey type")

    # Apply satisfaction deduction and trigger alert if threshold is crossed
    _apply_survey_deduction_and_alert(
        db=db, stay=current_stay, survey_type=survey_type, responses=responses
    )

    return ApiResponse(data="Survey submitted successfully.")


def _compute_survey_deduction(
    survey_type: Survey, responses: list, item_cote: float
) -> float:
    deduction = 0.0
    if survey_type == Survey.DAILY_ROOM:
        for val in responses[:4]:
            if val < 2.5:
                deduction += item_cote
    elif survey_type == Survey.ROOM_RECEPTION:
        for val in responses[:4]:
            if val < 2.5:
                deduction += 2 * item_cote
    elif survey_type == Survey.RESTAURANT:
        for i, val in enumerate(responses[:4]):
            if i == 3:
                if val == 1:
                    deduction += item_cote
            else:
                if val < 2.5:
                    deduction += item_cote
    return deduction


def _apply_survey_deduction_and_alert(
    db: Session, stay: Stay, survey_type: Survey, responses: list
) -> None:
    deduction = _compute_survey_deduction(
        survey_type, responses, stay.survey_item_cote or 0.0
    )
    if deduction <= 0:
        return

    old_score = stay.guest_satisfaction or 1.0
    new_score = max(0.0, old_score - deduction)
    stay.guest_satisfaction = new_score
    db.add(stay)
    db.flush()

    ns_settings = settings_controller.find_by_field(
        "namespace_id", stay.namespace_id
    )
    threshold = (
        ns_settings.get("satisfaction_threshold", 0.5) if ns_settings else 0.5
    )

    check_and_trigger_satisfaction_alert(
        old_score=old_score,
        new_score=new_score,
        threshold=threshold,
        namespace_id=stay.namespace_id,
        stay_id=stay.id,
        guest_id=stay.guest_id,
    )


@lru_cache
def list_namespace_main_dishes(namespace_id: int, meal_type: MealEnum, db=None):
    """
    Returns the list of dishes for the current day, given namespace and meal_type.
    """
    today = date.today()
    # Query for today's meal of the given type in the namespace
    meal = (
        db.query(Meal)
        .filter(
            Meal.namespace_id == namespace_id,
            Meal.meal_type == meal_type.value,
            Meal.meal_date == today,
        )
        .first()
    )
    if not meal:
        return []
    # Get all menu entries for this meal
    menu_entries = db.query(Menu).filter(Menu.meal_id == meal.id).all()
    dish_ids = [entry.dishes_id for entry in menu_entries]
    # Get all dishes for these ids
    dishes = db.query(Dishes).filter(Dishes.id.in_(dish_ids)).all()
    return [dish.to_dict() for dish in dishes]


def submit_dishes_survey(
    payload: DishesSurveySubmitPayload, current_guest: dict, db: Session
):
    """
    Submits a dishes survey for the current guest and stay.
    """
    # Validate all keys are valid dish ids
    dish_ids = list(payload.responses.keys())
    valid_dishes = db.query(Dishes).filter(Dishes.id.in_(dish_ids)).all()
    if len(valid_dishes) != len(dish_ids):
        raise HTTPException(status_code=400, detail="One or more dish ids are invalid.")
    # Get current stay
    stay = get_current_stay(db, current_guest["phone_number"])

    namespace_id = stay.namespace_id
    guest_phone_number = current_guest["phone_number"]
    # Create DishesSurvey rows
    for dish_id, score in payload.responses.items():
        survey = DishesSurvey(
            namespace_id=namespace_id,
            guest_phone_number=guest_phone_number,
            stay_id=stay.id,
            dish_id=dish_id,
            Q=score + 1,  # Assuming score is 0-4, convert to 1-5 scale
        )
        db.add(survey)
    db.commit()
    return {"detail": "Dishes survey submitted successfully."}
