import random
from src.app.globals.notification import send_push_notification
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from src.app.db.models import NamespaceSettings
from src.app.db.models import Namespace
from src.app.db.models import DailyRestaurantSurvey
from src.app.db.models import DailyRoomSatisfactionSurvey
from src.app.db.models import Stay
from src.app.db.models import RoomReceptionSurvey
from datetime import datetime,time
from zoneinfo import ZoneInfo
from src.app.globals.schema_models import UsersModel
from src.app.globals.schema_models import NamespaceModel
from fastapi import status
from dotmap import DotMap
from src.app.secrets.passwords import check_password
from src.app.globals.exceptions import ApiException
from .modelsOut import hotel_exist_error, invalid_credentials_error
from src.app.globals.error import dbError
from src.app.db.orm import get_db
from src.app.secrets.jwt import sign_jwt
from src.app.globals.emails import (
    send_email,
    send_account_under_review_email,
    send_suspicious_account_alert_to_commercial,
)
from src.settings import client, settings
from src.app.resourcesController import (
    users_controller,
    namespace_controller,
)
from src.app.globals.decorators import transactional
from src.app.routers.users.services import upload_user_avatar
import logging
from .templates import domain_template
import json
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def generate_otp():
    """Generates a 4-digit OTP."""
    return random.randint(1000, 9999)


def send_otp(push_token: str):
    """Sends an OTP code to the given push token."""

    otp = generate_otp()
    message = f"Your OTP code is: {otp}"
    notif_title = "Your Verification Code"
    send_push_notification(push_token, notif_title, message)
    print(f"opt: {otp}")
    return otp


def detect_time_zone(city: str, country: str) -> str:
    geolocator = Nominatim(user_agent="tz_finder")
    location = geolocator.geocode(f"{city}, {country}")
    if location:
        tf = TimezoneFinder()
        timezone = tf.timezone_at(lng=location.longitude, lat=location.latitude)
        return timezone
    return "Timezone not found"


def count_current_survey(db, namespace_id, phone_number):
    # Get settings for the namespace
    settings = (
        db.query(NamespaceSettings)
        .filter(NamespaceSettings.namespace_id == namespace_id)
        .first()
    )
    if not settings:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"NamespaceSettings not found for the given {namespace_id}.")

    restaurant_survey_time = settings.restaurant_survey_time
    room_survey_time = settings.room_survey_time

    # Get timezone for the namespace
    ns = db.query(Namespace.timezone).filter(Namespace.id == namespace_id).first()
    if not ns or not ns[0]:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"Namespace timezone not found for the given {namespace_id}.")
    namespace_tz = ns[0]

    tz = ZoneInfo(namespace_tz)
    now = datetime.now(tz)
    today = now.date()
    start_of_day = datetime.combine(today, time.min).replace(tzinfo=tz)
    end_of_day = datetime.combine(today, time.max).replace(tzinfo=tz)
    tz_restaurant_survey = datetime.combine(today, restaurant_survey_time, tzinfo=tz)
    tz_room_survey = datetime.combine(today, room_survey_time, tzinfo=tz)

    cnt = 0

    # Check if it's time for the restaurant survey and if the guest hasn't filled it today
    if now >= tz_restaurant_survey:
        restaurant_survey = (
            db.query(DailyRestaurantSurvey)
            .filter(
                DailyRestaurantSurvey.namespace_id == namespace_id,
                DailyRestaurantSurvey.guest_phone_number == phone_number,
                DailyRestaurantSurvey.created_at >= start_of_day,
                DailyRestaurantSurvey.created_at <= end_of_day,
            )
            .first()
        )
        if not restaurant_survey:
            cnt += 1

    # Extract the stay start date for the current guest in the current namespace
    stay = (
        db.query(Stay)
        .filter(
            Stay.guest_id == phone_number,
            Stay.namespace_id == namespace_id,
        )
        .order_by(Stay.start_date.desc())
        .first()
    )
    if stay and stay.start_date == today:
        # Check if room_reception_survey is filled by the guest for today
        room_reception_survey = (
            db.query(RoomReceptionSurvey)
            .filter(
                RoomReceptionSurvey.namespace_id == namespace_id,
                RoomReceptionSurvey.guest_phone_number == phone_number,
                RoomReceptionSurvey.created_at >= start_of_day,
                RoomReceptionSurvey.created_at <= end_of_day,
            )
            .first()
        )
        if not room_reception_survey:
            print("reception")
            cnt += 1
    # Check if it's time for the room survey and if the guest hasn't filled it today
    elif now >= tz_room_survey and stay.end_date != today:
        room_survey = (
            db.query(DailyRoomSatisfactionSurvey)
            .filter(
                DailyRoomSatisfactionSurvey.namespace_id == namespace_id,
                DailyRoomSatisfactionSurvey.guest_phone_number == phone_number,
                DailyRoomSatisfactionSurvey.created_at >= start_of_day,
                DailyRoomSatisfactionSurvey.created_at <= end_of_day,
            )
            .first()
        )
        if not room_survey:
            cnt += 1

    return cnt


@transactional
def handle_register_new_domain(payload, avatar, db=None):
    payload_dict = dict(payload)
    payload_map = DotMap(payload_dict)

    check_new_domain_result = check_new_domain(payload_dict)

    check_hotel = (
        db.query(Namespace)
        .filter(
            (
                (
                    Namespace.business_registration_number
                    == payload_map.business_registration_number
                )
                | (
                    Namespace.tax_identification_number
                    == payload_map.tax_identification_number
                )
                | (
                    (Namespace.hotel_name == payload_map.hotel_name)
                    & (Namespace.country == payload_map.country)
                )
            )
        )
        .first()
    )
    if check_hotel:
        raise ApiException(
            status_code=status.HTTP_409_CONFLICT, error=hotel_exist_error
        )
    user_dict = dict(UsersModel(**payload_dict))
    if avatar:
        user_dict["avatar_url"] = upload_user_avatar(avatar)

    namespace_dict = dict(NamespaceModel(**payload_dict))
    namespace_dict["hotel_website_url"] = str(namespace_dict.pop("hotel_website_url"))
    namespace_dict["timezone"] = detect_time_zone(
        namespace_dict["country"], namespace_dict["city"]
    )
    namespace = namespace_controller.create(namespace_dict, db=db, commit=False)

    namespace_id = namespace["id"]
    user_dict["namespace_id"] = namespace_id
    try:
        users_controller.create(user_dict, db=db, commit=False)
    except Exception as e:
        raise ApiException(status.HTTP_406_NOT_ACCEPTABLE, dbError(detail=str(e)))

    # owner_row = users_controller.find_by_field("user_email", payload_map.user_email)
    verification_link = f"{str(settings.application_url) + settings.email_confirmation_router}{sign_jwt(user_dict, expires=3600)}"
    if check_new_domain_result:
        send_email(
            payload_map.user_email,
            payload_map.first_name,
            verification_link,
        )
    else:
        # Send email to user informing them their account is under review
        try:
            send_account_under_review_email(
                to_email=payload_map.user_email, hotel_name=payload_map.hotel_name
            )
        except Exception as email_error:
            logger.error(
                f"Failed to send account under review email: {str(email_error)}"
            )
            # Continue even if email fails

        # Send alert to commercial team about suspicious account
        try:
            send_suspicious_account_alert_to_commercial(
                hotel_name=payload_map.hotel_name,
                user_email=payload_map.user_email,
                country=payload_map.country,
                city=payload_map.city,
            )
        except Exception as email_error:
            logger.error(
                f"Failed to send suspicious account alert to commercial team: {str(email_error)}"
            )
            # Continue even if email fails

    return {"data": "New domain registred successfully!"}


def handle_web_app_login(username: str, password: str, db):
    """Authenticate user with username (phone_number) and password."""
    # Query user by phone_number (username)
    user = users_controller.find_by_field("phone_number", username)

    if not user:
        raise ApiException(status.HTTP_401_UNAUTHORIZED, invalid_credentials_error)

    # Get hashed password from user
    hashed_password = (
        user.get("hashed_password") if isinstance(user, dict) else user.hashed_password
    )

    # Verify password using check_password
    if not check_password(password, hashed_password):
        raise ApiException(status.HTTP_401_UNAUTHORIZED, invalid_credentials_error)

    # Return JWT token
    return {"token": sign_jwt(user)}


def auto_validate(result: dict) -> bool:
    result = json.loads(result)

    return (
        result["hotel_public_presence"] == "FOUND"
        and result["domain_matches_hotel"] is True
        and result["confidence"] >= 0.6
    )


def check_new_domain(payload: dict):
    hotel_name = payload.get("hotel_name")
    country = payload.get("country")
    city = payload.get("city")
    user_email = payload.get("user_email")
    response = client.responses.create(
        model="gpt-5", tools=[{"type": "web_search"}], input=domain_template
    )
    result = response.output_text
    if not auto_validate(result):
        return False

    return True
