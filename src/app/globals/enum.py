from enum import Enum


class MealPlan(Enum):
    ep: str = "EP"  # European Plan
    bb: str = "B&B"  # Bed and Breakfast
    hb: str = "HB"  # Half Board
    fb: str = "FB"  # Full Board
    ais: str = "AIS"  # All Inclusive soft
    ai: str = "AI"  # All Inclusive Standard


class Survey(str, Enum):
    RESTAURANT: str = "restaurant"
    DAILY_ROOM: str = "daily_room"
    ROOM_RECEPTION: str = "room_reception"
    Meals: str = "meals"


class MealEnum(str, Enum):
    BREAKFAST: str = "breakfast"
    LUNCH: str = "lunch"
    DINNER: str = "dinner"


class JobType(str, Enum):
    """Enum for all available async job types in the system"""

    # Survey notification tasks
    DAILY_ROOM_SURVEY = "daily_room_survey"
    RESTAURANT_SURVEY = "restaurant_survey"
    ROOM_RECEPTION_SURVEY = "room_reception_survey"

    # Meal menu notification tasks
    BREAKFAST_MENU = "breakfast_menu"
    LUNCH_MENU = "lunch_menu"
    DINNER_MENU = "dinner_menu"

    # Meal reminder tasks
    BREAKFAST_REMINDER = "breakfast_reminder"
    LUNCH_REMINDER = "lunch_reminder"
    DINNER_REMINDER = "dinner_reminder"


class CachingCollectionName(str, Enum):
    """Enum for Firestore collection names used in caching"""

    # Meal reminder notifications
    MEAL_REMINDERS_NOTIF_TITLES: str = "meal_reminders_notif_titles"
    MEAL_REMINDERS_NOTIF_BODY: str = "meal_reminders_notif_body"

    # Daily room survey notifications
    DAILY_ROOM_SURVEY_NOTIF_TITLES: str = "daily_room_survey_notif_titles"

    # Restaurant survey notifications
    RESTAURANT_SURVEY_NOTIF_TITLES: str = "restaurant_survey_notif_titles"

    # Room reception survey notifications
    ROOM_RECEPTION_SURVEY_NOTIF_TITLES: str = "room_reception_survey_notif_titles"

    # Meal menu notifications
    MEAL_MENU_NOTIF_TITLES: str = "meal_menu_notif_titles"

    # Chat room welcome messages
    CHAT_ROOM_WELCOME_MESSAGE: str = "chat_room_welcome_message"

    # Task deduplication (separate collections for each worker type)
    PROCESSED_PUBSUB_TASKS: str = "processed_pubsub_tasks"
    PROCESSED_CLOUD_TASKS: str = "processed_cloud_tasks"


class NotifMediaText(str, Enum):
    Image: str = "Sent an image."
    Video: str = "Sent a video."
    Audio: str = "Sent an audio."
