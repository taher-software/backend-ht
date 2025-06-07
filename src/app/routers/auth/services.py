from twilio.rest import Client
import random
from src.app.globals.notification import send_push_notification
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

# Replace these with your Twilio credentials
TWILIO_ACCOUNT_SID = "your_account_sid"
TWILIO_AUTH_TOKEN = "your_auth_token"
TWILIO_PHONE_NUMBER = "your_twilio_phone_number"


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
