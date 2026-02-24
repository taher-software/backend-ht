from fastapi import HTTPException

from src.app.db.models.dishes import Dishes
from src.app.db.models.meals import Meal
from src.app.db.models.menu import Menu
from src.app.db.models.namespace import Namespace
from src.app.globals.decorators import transactional
from src.app.globals.enum import MealEnum
from src.app.resourcesController import meal_controller, menu_controller, dishes_controller
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import selectinload

# Logic for meals endpoints will be implemented here


def create_meal_with_menu(payload, current_user, db):
    # Check allowed roles
    # allowed_roles = {"owner", "admin", "supervisor", "dining_supervisor"}
    # if current_user.get("role") not in allowed_roles:
    # raise HTTPException(
    # status_code=403, detail="You do not have permission to create meals."
    # )

    namespace_id = current_user.get("namespace_id")
    if not namespace_id:
        raise HTTPException(
            status_code=400, detail="Namespace not found for current user."
        )

    # Validate all dishes_ids belong to the same namespace
    dishes = db.query(Dishes).filter(Dishes.id.in_(payload.dishes_ids)).all()
    if len(dishes) != len(payload.dishes_ids):
        raise HTTPException(status_code=400, detail="Some dishes do not exist.")
    for dish in dishes:
        if dish.namespace_id != namespace_id:
            raise HTTPException(
                status_code=400, detail="All dishes must belong to your namespace."
            )

    @transactional
    def _create(db=db):
        meal = Meal(
            meal_type=payload.meal_type,
            namespace_id=namespace_id,
            meal_date=payload.meal_date,
        )
        db.add(meal)
        db.flush()  # get meal.id
        for dish_id in payload.dishes_ids:
            menu = Menu(dishes_id=dish_id, meal_id=meal.id)
            db.add(menu)
        return meal.to_dict()

    return _create()


def get_upcoming_meals(namespace_id: int, db=None):
    
    today = date.today()
    return (
        db.query(Meal)
        .options(selectinload(Meal.menus))
        .filter(Meal.namespace_id == namespace_id, Meal.meal_date >= today)
        .order_by(Meal.meal_date)
        .all()
    )


def get_meal_by_id(meal_id: int, namespace_id: int, db=None):

    meal = (
        db.query(Meal)
        .options(selectinload(Meal.menus))
        .filter(Meal.id == meal_id)
        .first()
    )
    if not meal:
        raise HTTPException(status_code=404, detail=f"Meal with id {meal_id} not found")
    if meal.namespace_id != namespace_id:
        raise HTTPException(status_code=403, detail="Meal does not belong to your namespace")
    return meal


@transactional
def update_meal(meal_id: int, namespace_id: int, payload, db=None):
    meal = meal_controller.find_by_id(meal_id)
    if not meal:
        raise HTTPException(status_code=404, detail=f"Meal with id {meal_id} not found")
    if meal["namespace_id"] != namespace_id:
        raise HTTPException(status_code=403, detail="Meal does not belong to your namespace")

    update_data = payload.dict(exclude_unset=True)

    # Update meal fields
    meal_update = {}
    if "meal_type" in update_data:
        meal_update["meal_type"] = update_data["meal_type"]
    if "meal_date" in update_data:
        meal_update["meal_date"] = update_data["meal_date"]
    if meal_update:
        meal_controller.update(meal_id, meal_update, db=db, commit=False)

    # Replace menus if dishes_ids provided
    if "dishes_ids" in update_data:
        dishes_ids = update_data["dishes_ids"]
        for dish_id in dishes_ids:
            dish = dishes_controller.find_by_id(dish_id)
            if not dish:
                raise HTTPException(status_code=400, detail=f"Dish with id {dish_id} does not exist.")
            if dish["namespace_id"] != namespace_id:
                raise HTTPException(status_code=400, detail="All dishes must belong to your namespace.")
        # Delete existing menus for this meal
        existing_menus = db.query(Menu).filter(Menu.meal_id == meal_id).all()
        for m in existing_menus:
            menu_controller.delete(m.id, commit=False, db=db)
        # Create new menus
        for dish_id in dishes_ids:
            menu_controller.create({"dishes_id": dish_id, "meal_id": meal_id}, db=db, commit=False)

    return (
        db.query(Meal)
        .options(selectinload(Meal.menus))
        .filter(Meal.id == meal_id)
        .first()
    )


def delete_meal(meal_id: int, namespace_id: int):
    meal = meal_controller.find_by_id(meal_id)
    if not meal:
        raise HTTPException(status_code=404, detail=f"Meal with id {meal_id} not found")
    if meal["namespace_id"] != namespace_id:
        raise HTTPException(status_code=403, detail="Meal does not belong to your namespace")
    meal_controller.delete(meal_id, db=meal_controller.db)


@transactional
def delete_meals_batch(meal_ids: list[int], namespace_id: int, db=None):
    for meal_id in meal_ids:
        meal = meal_controller.find_by_id(meal_id)
        if not meal:
            raise HTTPException(status_code=404, detail=f"Meal with id {meal_id} not found")
        if meal["namespace_id"] != namespace_id:
            raise HTTPException(status_code=403, detail=f"Meal with id {meal_id} does not belong to your namespace")
        meal_controller.delete(meal_id, commit=False, db=db)
    return len(meal_ids)


# ============================================================================
# Meal Reminder Helper Functions
# ============================================================================


def get_late_namespaces(
    meal_time_field: str = "breakfast_menu_time",
    meal_type: MealEnum = MealEnum.BREAKFAST,
    db=None,
):

    namespaces = db.query(Namespace).all()

    results = []
    for ns in namespaces:
        if not ns.settings:
            continue  # skip if no settings
        tz = ZoneInfo(ns.timezone)
        meal_time = datetime.combine(
            date.today(), getattr(ns.settings, meal_time_field), tzinfo=tz
        )
        now_tz = datetime.now(tz)
        # Only proceed if meal_time is at most 2 hours ahead
        time_diff = (meal_time - now_tz).total_seconds() / 60  # minutes
        if not (0 <= time_diff <= 120):
            continue
        # --- Begin logic ---
        check_date = date.today()
        if meal_type == MealEnum.BREAKFAST:
            # Check if breakfast_menu_time is AM or PM
            menu_time = getattr(ns.settings, meal_time_field)
            if menu_time.hour >= 12:  # PM
                check_date = date.today() + timedelta(days=1)
            # else: AM, keep today
        # For breakfast, check for tomorrow if PM, else today
        # For other meals, always check today
        meal_exists = (
            db.query(Meal)
            .filter(
                Meal.namespace_id == ns.id,
                Meal.meal_type == meal_type,
                Meal.meal_date == check_date,
            )
            .first()
        )
        if not meal_exists:
            results.append(ns.id)
    # --- End logic ---
    return results
