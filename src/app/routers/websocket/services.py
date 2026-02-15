from fastapi import status, WebSocket
import logging
import tempfile
import os
from datetime import datetime
from src.settings import client
from src.app.resourcesController import (
    users_controller,
    guest_controller,
    message_controller,
)
from src.app.db.models import ChatRoom, OwnerType, Claim, Stay
from sqlalchemy.orm import selectinload
from src.app.globals.exceptions import ApiException
from src.app.globals.decorators import transactional
from src.app.globals.notification import send_push_notification
from src.app.globals.utils import translate_text, transcribe_audio_from_gcs_link
from src.app.globals.enum import NotifMediaText
from src.app.gcp.gcs import storage_client
from src.app.gcp import get_pubsub_publisher
from src.app.routers.chat.services import (
    send_notification_to_recipient,
)

logger = logging.getLogger(__name__)


def get_receipient_language(recipient: dict, is_guest: bool) -> str:
    """
    Get the preferred language of the recipient.

    Args:
        recipient: Recipient record (user or guest)
        is_guest: True if recipient is guest, False if user

    Returns:
        str: Preferred language of the recipient
    """
    pref_language = (
        recipient.get("pref_language")
        if isinstance(recipient, dict)
        else recipient.pref_language
    )
    return pref_language if pref_language else None


def generate_voice_and_upload_to_gcs(text: str) -> str:
    """
    Generate voice audio from text and upload to GCS.

    Args:
        text: Text to convert to speech

    Returns:
        str: GCS URL of uploaded audio file

    Raises:
        Exception: If voice generation or upload fails
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_file = os.path.join(temp_dir, "voice_output.mp3")

            # Generate speech from text using OpenAI TTS
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="nova",
                input=text,
            ) as response:
                response.stream_to_file(destination_file)

            # Upload to GCS
            voice_url = storage_client.upload_to_bucket(
                "voice-messages-url-bucket",
                destination_file,
                f"voice_messages_{datetime.utcnow().isoformat()}.mp3",
            )

            logger.info(
                f"Successfully generated and uploaded voice to GCS: {voice_url}"
            )
            return voice_url

    except Exception as e:
        logger.error(f"Failed to generate voice and upload to GCS: {str(e)}")
        raise


@transactional
def handle_websocket_message(
    room_id: int,
    current_user: dict,
    message_type: str,
    text: str = None,
    image_url: str = None,
    video_url: str = None,
    voice_url: str = None,
    duration: float = None,
    guest_connections: dict = None,
    user_connections: dict = None,
    db=None,
):
    """
    Handle WebSocket message and create appropriate Message record.

    Args:
        room_id: ID of the chat room
        current_user: Current authenticated user (user or guest)
        message_type: Type of message (text, image, video, audio)
        text: Text content (optional)
        image_url: Image URL (optional)
        video_url: Video URL (optional)
        voice_url: Voice/audio URL (optional)
        duration: Duration of voice/audio message in seconds (optional)
        db: Database session

    Returns:
        dict: Created message data

    Raises:
        ApiException: If validation fails
    """
    # Find the ChatRoom by room_id
    chat_room = (
        db.query(ChatRoom)
        .filter(ChatRoom.id == room_id, ChatRoom.active == True)
        .first()
    )

    if not chat_room:
        raise ApiException(
            status.HTTP_404_NOT_FOUND,
            {
                "type": "chat_room_not_found",
                "message": f"No active chat room found with ID {room_id}",
            },
        )

    # Determine if current user is a guest or user
    is_guest = "phone_number" in current_user and "id" not in current_user
    is_user = "id" in current_user
    text_notif = None
    user = None
    guest = None

    # Get user associated with this chat room
    user = users_controller.find_by_id(chat_room.user_id)
    if not user:
        raise ApiException(
            status.HTTP_404_NOT_FOUND,
            {
                "type": "user_not_found",
                "message": "User not found for chat room",
            },
        )
    if is_user and user.get("id") != current_user.get("id"):
        raise ApiException(
            status.HTTP_403_FORBIDDEN,
            {
                "type": "forbidden",
                "message": "User not authorized to send message in this chat room",
            },
        )

    # Get guest associated with this chat room
    guest = guest_controller.find_by_id(chat_room.guest_id)
    if not guest:
        raise ApiException(
            status.HTTP_404_NOT_FOUND,
            {
                "type": "guest_not_found",
                "message": "Guest not found for chat room",
            },
        )
    if is_guest and guest.get("phone_number") != current_user.get("phone_number"):
        raise ApiException(
            status.HTTP_403_FORBIDDEN,
            {
                "type": "forbidden",
                "message": "Guest not authorized to send message in this chat room",
            },
        )
    # Get user's preferred language
    user_pref_language = get_receipient_language(user, is_guest=False)

    # Get guest's preferred language
    guest_pref_language = get_receipient_language(guest, is_guest=True)

    # Initialize message data
    message_data = {
        "room_id": chat_room.id,
        "namespace_id": chat_room.namespace_id,
        "owner_type": OwnerType.guest.value if is_guest else OwnerType.user.value,
        "message_type": message_type,
    }

    # Handle text messages with translation
    if message_type == "text" and text:
        if is_guest:
            # Guest is sending message
            guest_text_version = text
            # Translate text to user's language
            user_text_version = (
                translate_text(text, user_pref_language) if user_pref_language else text
            )

            message_data["guest_text_version"] = guest_text_version
            message_data["user_text_version"] = user_text_version
            text_notif = user_text_version

        elif is_user:
            # User is sending message
            user_text_version = text

            # Translate text to guest's language
            guest_text_version = (
                translate_text(text, guest_pref_language)
                if guest_pref_language
                else text
            )

            message_data["guest_text_version"] = guest_text_version
            message_data["user_text_version"] = user_text_version

            text_notif = guest_text_version

    # Handle media messages (image, video, audio)
    if message_type == "image" and image_url:
        message_data["image_url"] = image_url
        if is_guest:
            text_notif = (
                translate_text(NotifMediaText.Image.value, user_pref_language)
                if user_pref_language
                else NotifMediaText.Image.value
            )
        else:
            text_notif = (
                translate_text(NotifMediaText.Image.value, guest_pref_language)
                if guest_pref_language
                else NotifMediaText.Image.value
            )

    if message_type == "video" and video_url:
        message_data["video_url"] = video_url
        if is_guest:
            text_notif = (
                translate_text(NotifMediaText.Video.value, user_pref_language)
                if user_pref_language
                else NotifMediaText.Video.value
            )
        else:
            text_notif = (
                translate_text(NotifMediaText.Video.value, guest_pref_language)
                if guest_pref_language
                else NotifMediaText.Video.value
            )
    if message_type == "audio" and voice_url:
        voice_text = transcribe_audio_from_gcs_link(voice_url)
        # Add duration to message data if provided
        if duration is not None:
            message_data["duration"] = duration
        if is_guest:
            message_data["guest_voice_url"] = voice_url
            user_voice_text = (
                translate_text(voice_text, user_pref_language)
                if user_pref_language
                else voice_text
            )
            text_notif = (
                translate_text(NotifMediaText.Audio.value, user_pref_language)
                if user_pref_language
                else NotifMediaText.Audio.value
            )
            message_data["user_voice_url"] = generate_voice_and_upload_to_gcs(
                user_voice_text
            )
        else:
            message_data["user_voice_url"] = voice_url
            guest_voice_text = (
                translate_text(voice_text, guest_pref_language)
                if guest_pref_language
                else voice_text
            )
            text_notif = (
                translate_text(NotifMediaText.Audio.value, guest_pref_language)
                if guest_pref_language
                else NotifMediaText.Audio.value
            )
            message_data["guest_voice_url"] = generate_voice_and_upload_to_gcs(
                guest_voice_text
            )

    # Create the message
    message = message_controller.create(message_data, db=db, commit=False)

    logger.info(
        f"Message created for room {room_id} by {'guest' if is_guest else 'user'}"
    )

    message = message if isinstance(message, dict) else message.to_dict()

    # Convert datetime objects to ISO format strings for JSON serialization
    for key, value in message.items():
        if isinstance(value, datetime):
            message[key] = value.isoformat()

    # extract connections to notify
    connections = []

    if message["owner_type"] == "guest":
        connections = user_connections.get(user["id"], [])
    if message["owner_type"] == "user":
        connections = guest_connections.get(guest["phone_number"], [])

    if not connections:
        logger.warning(
            f"No active connections for recipient: {guest['phone_number'] if is_user else user['id']}"
        )

    # Load claim with stay and room relationships for notification title
    claim = (
        db.query(Claim)
        .options(selectinload(Claim.stay).selectinload(Stay.room))
        .filter(Claim.id == chat_room.claim_id)
        .first()
    )

    send_notification_to_recipient(
        recipient=guest if is_user else user,
        claim=claim,
        message_text=text_notif,
        is_guest=not is_guest,
    )

    return dict(message=message, connections=connections)


def cleanup_websocket_connections(
    websocket: WebSocket,
    guest_id: str = None,
    user_id: int = None,
    guest_connections: dict = None,
    user_connections: dict = None,
) -> None:
    """
    Clean up WebSocket connections from connection dictionaries.

    Removes the websocket from guest_connections and/or user_connections
    dictionaries. If a connection list becomes empty after removal,
    the key is deleted from the dictionary.

    Args:
        websocket: WebSocket connection to remove
        guest_id: Guest phone number (optional)
        user_id: User ID (optional)
        guest_connections: Dictionary mapping guest_id to list of websockets (optional)
        user_connections: Dictionary mapping user_id to list of websockets (optional)

    Returns:
        None
    """
    # Clean up guest connections
    if guest_id and guest_connections and guest_id in guest_connections:
        if websocket in guest_connections[guest_id]:
            guest_connections[guest_id].remove(websocket)
        if not guest_connections[guest_id]:
            del guest_connections[guest_id]
        logger.info(f"Cleaned up guest connection for guest_id: {guest_id}")

    # Clean up user connections
    if user_id and user_connections and user_id in user_connections:
        if websocket in user_connections[user_id]:
            user_connections[user_id].remove(websocket)
        if not user_connections[user_id]:
            del user_connections[user_id]
        logger.info(f"Cleaned up user connection for user_id: {user_id}")
