# ============================================================================
# Import Per-Namespace Meal Reminder Tasks
# ============================================================================

from .add_meals_reminder import (
    send_notif_breakfast_menu_reminder_for_namespace,
    send_notif_lunch_menu_reminder_for_namespace,
    send_notif_dinner_menu_reminder_for_namespace,
)

from .daily_room_survey import send_notif_daily_room_satisf_for_namespace

from .restaurant_survey import send_notif_restaurant_survey_for_namespace

from .room_reception import send_notif_room_reception_satisf_for_guest

from .meals_notifs import (
    send_notif_dinner_menu_for_namespace,
    send_notif_lunch_menu_for_namespace,
    send_notif_breakfast_menu_for_namespace,
)
