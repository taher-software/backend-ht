from src.app.db.controller import dbController
from src.app.db.models import (
    Namespace,
    Users,
    Guest,
    Claim,
    Room,
    Stay,
    NamespaceSettings,
)
from src.app.db.models import (
    DailyRoomSatisfactionSurvey,
    RoomReceptionSurvey,
    DailyRestaurantSurvey,
    DishesSurvey,
    Dishes,
    QueueRootCause,
    ChatRoom,
    Message,
    Meal,
    Menu,
    Housekeeper,
)

users_controller = dbController(Users)
namespace_controller = dbController(Namespace)
guest_controller = dbController(Guest)
claim_controller = dbController(Claim)
room_controller = dbController(Room)
stay_controller = dbController(Stay)
settings_controller = dbController(NamespaceSettings)
daily_room_satisfaction_survey_controller = dbController(
    DailyRoomSatisfactionSurvey
)
room_reception_survey_controller = dbController(RoomReceptionSurvey)
daily_restaurant_survey_controller = dbController(DailyRestaurantSurvey)
dishes_survey_controller = dbController(DishesSurvey)
dishes_controller = dbController(Dishes)
queue_root_cause_controller = dbController(QueueRootCause)
chatRoom_controller = dbController(ChatRoom)
message_controller = dbController(Message)
meal_controller = dbController(Meal)
menu_controller = dbController(Menu)
housekeeper_controller = dbController(Housekeeper)
