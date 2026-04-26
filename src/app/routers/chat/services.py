from fastapi import status, WebSocket
import logging
from src.app.db.orm import get_db
from src.settings import client
from src.app.resourcesController import (
    users_controller,
    claim_controller,
    guest_controller,
    chatRoom_controller,
    message_controller,
)
from src.app.db.models import ChatRoom, Message, Claim, Stay, OwnerType
from src.app.globals.exceptions import ApiException
from .modelsOut import (
    claim_not_found_error,
    guest_not_found_error,
    namespace_mismatch_error,
    stay_not_found_error,
    invalid_stay_dates_error,
    stay_namespace_mismatch_error,
    no_device_token_error,
    notification_failed_error,
    ChatRoomOut,
    MessageOut,
)

from functools import lru_cache
from src.app.gcp import firestore_client, pubsub_publisher
import backoff
from src.app.globals.enum import CachingCollectionName
from datetime import datetime, date, timedelta
from sqlalchemy import and_, func, desc
from sqlalchemy.orm import selectinload
from src.app.globals.decorators import transactional
from src.app.globals.notification import send_push_notification
from src.app.globals.utils import translate_text
from src.app.globals.enum import NotifMediaText
from src.app.globals.utils import transcribe_audio_from_gcs_link
import tempfile
import os
from src.app.gcp.gcs import storage_client
from src.app.gcp import get_pubsub_publisher

logger = logging.getLogger(__name__)


def send_notification_to_recipient(
    recipient: dict,
    claim: dict,
    message_text: str,
    is_guest: bool,
):
    """
    Send push notification to recipient (user or guest) about new chat message.

    Args:
        recipient: Recipient record (user or guest)
        claim: Claim record
        message_text: Message text to include in notification
        is_guest: True if recipient is guest, False if user
    """
    try:
        device_token = (
            recipient.get("current_device_token")
            if isinstance(recipient, dict)
            else recipient.current_device_token
        )

        if device_token:
            notification_title = create_message_notif_title(
                claim, recipient_is_guest=is_guest
            )
            notification_body = build_preview(message_text)

            send_push_notification(
                expo_push_token=device_token,
                title=notification_title,
                message=notification_body,
                notif_level="message",
            )

            logger.info(
                f"Push notification sent to {'guest' if is_guest else 'user'} {recipient.get('id', 'unknown')}"
            )
        else:
            logger.warning(
                f"{'Guest' if is_guest else 'User'} {recipient.get('id', 'unknown')} has no device token, skipping push notification"
            )

    except Exception as e:
        logger.error(
            f"Failed to send push notification to {'guest' if is_guest else 'user'} {recipient.get('id', 'unknown')}: {str(e)}"
        )


def create_message_notif_title(claim, recipient_is_guest: bool = True) -> str:
    """
    Create notification title for new chat message.

    Args:
        claim: Claim record (dict or model instance)
        recipient_is_guest: True if notification is for a guest, False if for hotel staff/user

    Returns:
        str: Notification title
            - For guests: "Claim: {claim_title} – New message"
            - For staff: "Room: {room_number} – New message"
    """
    print(f"Received Claim: {claim}")
    print(f"recipient_is_guest: {recipient_is_guest}")

    room_number = "Unknown"
    if recipient_is_guest:
        claim_title = (
            claim.get("claim_title") if isinstance(claim, dict) else claim.claim_title
        )
        return f"Claim: {claim_title} – New message"

    # For staff notifications, show room number
    if isinstance(claim, dict):
        # If claim is a dict, we need to get the stay and room information
        # This requires additional database queries or the dict must contain the nested data
        stay = claim.get("stay")
        print(f"Extracted Stay from Claim: {stay}")
        if stay:
            room = stay.get("room") if isinstance(stay, dict) else stay.room
            print(f"Extracted Room from Stay: {room}")
            room_number = (
                room.get("room_number") if isinstance(room, dict) else room.room_number
            )
            print(f"Determined Room Number: {room_number}")
    else:
        print(f"Claim ORM Object: {claim}")
        # ORM object - can access relationships directly
        room_number = claim.stay.room.room_number
        print(f"Determined Room Number from ORM: {room_number}")

    print(f"Final Room Number for Notification: {room_number}")

    return f"Room: {room_number} – New message"


def build_preview(message: str, limit=50):
    clean = message.replace("\n", " ").strip()
    return clean[:limit] + ("…" if len(clean) > limit else "")


def translate_welcome_message(target_language: str) -> str:
    """
    Translate welcome message to target language with Firestore caching.

    Args:
        target_language: Target language for translation

    Returns:
        str: Translated welcome message
    """
    # English welcome message
    english_text = (
        "Hello, Welcome. We are reviewing your claim and will assist you shortly."
    )

    # If target language is English, return original text
    if target_language.lower() in ["english", "en"]:
        return english_text

    # Check Firestore cache for existing translation
    collection_name = CachingCollectionName.CHAT_ROOM_WELCOME_MESSAGE.value
    existing_translation = firestore_client.get_document(
        collection_name=collection_name, document_id=target_language.lower()
    )

    if existing_translation:
        logger.info(f"Retrieved cached welcome message for language: {target_language}")
        return existing_translation.get("translated_text", english_text)

    # Translate using AI if not cached
    logger.info(f"Translating welcome message to {target_language}")
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are a professional translation assistant specializing in customer service communications.
Translate the following English text to {target_language} while maintaining:
- Professional and welcoming tone
- Clarity and conciseness
- Cultural appropriateness

IMPORTANT: Return ONLY the translated text without any additional explanations, notes, or formatting.""",
            },
            {"role": "user", "content": english_text},
        ],
    )

    translated_text = completion.choices[0].message.content.strip()

    # Cache the translation in Firestore
    firestore_client.create_document(
        collection_name=collection_name,
        document_id=target_language.lower(),
        data={
            "translated_text": translated_text,
            "source_language": "english",
            "target_language": target_language.lower(),
        },
    )

    logger.info(f"Cached welcome message for language: {target_language}")
    return translated_text


@transactional
def handle_initialize_chat(claim_id: int, current_user: dict, db=None) -> dict:
    """
    Initialize a chat room for a specific claim with welcome message.

    Args:
        claim_id: ID of the claim
        current_user: Current authenticated user
        db: Database session

    Returns:
        dict: ChatRoom data with welcome message

    Raises:
        ApiException: If validation fails
    """
    # Retrieve the claim by ID
    claim = claim_controller.find_by_id(claim_id)

    if not claim:
        raise ApiException(status.HTTP_404_NOT_FOUND, claim_not_found_error)

    # Get claim namespace and user namespace
    claim_namespace_id = (
        claim.get("namespace_id") if isinstance(claim, dict) else claim.namespace_id
    )
    user_namespace_id = (
        current_user.get("namespace_id")
        if isinstance(current_user, dict)
        else current_user.namespace_id
    )

    # Ensure user belongs to the same namespace as the claim
    if claim_namespace_id != user_namespace_id:
        raise ApiException(status.HTTP_403_FORBIDDEN, namespace_mismatch_error)

    # Return existing chat room if already associated with this claim
    existing_room = chatRoom_controller.find_by_field("claim_id", claim_id)
    if existing_room:
        return {"chat_room": existing_room}

    # Extract guest associated with the claim
    guest_id = claim.get("guest_id") if isinstance(claim, dict) else claim.guest_id
    guest = guest_controller.find_by_id(guest_id)

    if not guest:
        raise ApiException(status.HTTP_404_NOT_FOUND, guest_not_found_error)

    # Retrieve current stay for the guest
    today = date.today()
    current_stay = (
        db.query(Stay)
        .filter(
            and_(
                Stay.guest_id == guest_id,
                Stay.start_date <= today,
                Stay.end_date >= today,
            )
        )
        .first()
    )

    if not current_stay:
        raise ApiException(status.HTTP_404_NOT_FOUND, stay_not_found_error)

    # Verify today is within stay dates
    if not (current_stay.start_date <= today <= current_stay.end_date):
        raise ApiException(status.HTTP_400_BAD_REQUEST, invalid_stay_dates_error)

    # Ensure stay namespace matches claim namespace
    if current_stay.namespace_id != claim_namespace_id:
        raise ApiException(status.HTTP_400_BAD_REQUEST, stay_namespace_mismatch_error)

    # Get user ID
    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user["id"]
    )

    # Create new ChatRoom record using controller
    chat_room_data = {
        "user_id": user_id,
        "guest_id": guest_id,
        "claim_id": claim_id,
        "stay_id": current_stay.id,
        "namespace_id": claim_namespace_id,
        "active": True,
    }
    chat_room = chatRoom_controller.create(chat_room_data, db=db, commit=False)

    # Get chat room ID
    chat_room_id = chat_room.get("id") if isinstance(chat_room, dict) else chat_room.id

    # Get user preferred language (default to English)
    user_pref_language = (
        current_user.get("pref_language")
        if isinstance(current_user, dict)
        else current_user.pref_language
    )
    user_language = user_pref_language if user_pref_language else "english"

    # Get guest preferred language (default to English)
    guest_pref_language = (
        guest.get("pref_language") if isinstance(guest, dict) else guest.pref_language
    )
    guest_language = guest_pref_language if guest_pref_language else "english"

    # Translate welcome message for user
    user_text_version = translate_welcome_message(user_language)

    # Translate welcome message for guest
    guest_text_version = translate_welcome_message(guest_language)

    # Create welcome message using controller
    message_data = {
        "room_id": chat_room_id,
        "namespace_id": claim_namespace_id,
        "owner_type": OwnerType.user.value,
        "guest_text_version": guest_text_version,
        "user_text_version": user_text_version,
        "message_type": "text",
    }
    welcome_message = message_controller.create(message_data, db=db, commit=False)

    logger.info(
        f"Chat room {chat_room_id} initialized for claim {claim_id} by user {user_id} with welcome message"
    )

    # Send push notification to guest about new message
    send_notification_to_recipient(
        recipient=guest, claim=claim, message_text=guest_text_version, is_guest=True
    )
    return {
        "chat_room": chat_room if isinstance(chat_room, dict) else chat_room.to_dict(),
        "welcome_message": (
            welcome_message
            if isinstance(welcome_message, dict)
            else welcome_message.to_dict()
        ),
    }


def get_chat_rooms(current_user: dict, db) -> list:
    """
    Get list of active chat rooms for current user or guest.

    For users: Returns all active chat rooms where the user is involved.
    For guests: First checks if guest has an active stay (end_date > today),
                then returns all chat rooms for that stay.

    Args:
        current_user: Current authenticated user (user or guest) from JWT token
        db: Database session

    Returns:
        list: List of chat rooms with stay and room information loaded

    Raises:
        ApiException: If guest has no active stay or other validation fails
    """
    # Determine if current user is a guest or user
    is_guest = "phone_number" in current_user and "id" not in current_user
    is_user = "id" in current_user

    # Subquery to get the latest message created_at for each chat room
    latest_message_subq = (
        db.query(
            Message.room_id,
            func.max(Message.created_at).label("latest_message_at"),
        )
        .group_by(Message.room_id)
        .subquery()
    )

    if is_user:
        # For users: list all active chat rooms where user is involved
        user_id = current_user.get("id")
        cutoff = datetime.now() - timedelta(hours=24)

        chat_rooms = (
            db.query(ChatRoom)
            .outerjoin(
                latest_message_subq, ChatRoom.id == latest_message_subq.c.room_id
            )
            .options(
                selectinload(ChatRoom.stay).selectinload(Stay.room),
                selectinload(ChatRoom.claim),
                selectinload(ChatRoom.messages),
                selectinload(ChatRoom.user),
                selectinload(ChatRoom.guest),
            )
            .filter(
                ChatRoom.user_id == user_id,
                ChatRoom.active == True,
                ChatRoom.created_at >= cutoff,
            )
            .order_by(desc(latest_message_subq.c.latest_message_at))
            .all()
        )

    elif is_guest:
        # For guests: check if they have an active stay first
        guest_phone = current_user.get("phone_number")
        today = date.today()

        # Find active stay for guest (end_date > today)
        active_stay = (
            db.query(Stay)
            .filter(Stay.guest_id == guest_phone, Stay.end_date > today)
            .first()
        )

        if not active_stay:
            raise ApiException(
                status.HTTP_404_NOT_FOUND,
                {
                    "type": "no_active_stay",
                    "message": "Guest has no active stay",
                },
            )

        # Get all chat rooms for this guest with the active stay
        chat_rooms = (
            db.query(ChatRoom)
            .outerjoin(
                latest_message_subq, ChatRoom.id == latest_message_subq.c.room_id
            )
            .options(
                selectinload(ChatRoom.stay).selectinload(Stay.room),
                selectinload(ChatRoom.claim),
                selectinload(ChatRoom.messages),
                selectinload(ChatRoom.user),
                selectinload(ChatRoom.guest),
            )
            .filter(
                ChatRoom.guest_id == guest_phone,
                ChatRoom.stay_id == active_stay.id,
                ChatRoom.active == True,
            )
            .order_by(desc(latest_message_subq.c.latest_message_at))
            .all()
        )

    else:
        raise ApiException(
            status.HTTP_401_UNAUTHORIZED,
            {"type": "invalid_user", "message": "Invalid user credentials"},
        )

    # Convert ORM objects to Pydantic models (automatically serializes nested relationships)
    return [ChatRoomOut.from_orm(chat_room) for chat_room in chat_rooms]


def get_chat_room_messages(chat_room_id: int, current_user: dict, db) -> dict:
    """
    Get all messages for a specific chat room along with partner information.

    Args:
        chat_room_id: ID of the chat room
        current_user: Current authenticated user (user or guest) from JWT token
        db: Database session

    Returns:
        dict: Dictionary containing:
            - messages: List of messages sorted by created_at ascending
            - partner: Partner information (user if current is guest, guest if current is user)

    Raises:
        ApiException: If chat room not found or user not authorized
    """
    # Determine if current user is a guest or user
    is_guest = "phone_number" in current_user and "id" not in current_user
    is_user = "id" in current_user

    # Fetch chat room with messages, user, and guest eagerly loaded
    chat_room = (
        db.query(ChatRoom)
        .options(
            selectinload(ChatRoom.messages),
            selectinload(ChatRoom.user),
            selectinload(ChatRoom.guest),
        )
        .filter(ChatRoom.id == chat_room_id)
        .first()
    )

    if not chat_room:
        raise ApiException(
            status.HTTP_404_NOT_FOUND,
            {
                "type": "chat_room_not_found",
                "message": f"Chat room with ID {chat_room_id} not found",
            },
        )

    # Validate that current user belongs to this chat room and get partner
    partner = None
    if is_user:
        user_id = current_user.get("id")
        if chat_room.user_id != user_id:
            raise ApiException(
                status.HTTP_403_FORBIDDEN,
                {
                    "type": "forbidden",
                    "message": "User does not belong to this chat room",
                },
            )
        # Partner is the guest
        partner = chat_room.guest.to_dict() if chat_room.guest else None
    elif is_guest:
        guest_phone = current_user.get("phone_number")
        if chat_room.guest_id != guest_phone:
            raise ApiException(
                status.HTTP_403_FORBIDDEN,
                {
                    "type": "forbidden",
                    "message": "Guest does not belong to this chat room",
                },
            )
        # Partner is the user
        partner = chat_room.user.to_dict() if chat_room.user else None
    else:
        raise ApiException(
            status.HTTP_401_UNAUTHORIZED,
            {"type": "invalid_user", "message": "Invalid user credentials"},
        )

    # Sort messages by created_at ascending
    messages = sorted(chat_room.messages, key=lambda m: m.created_at)

    # Convert messages to Pydantic models
    return {
        "messages": [MessageOut.from_orm(message) for message in messages],
        "partner": partner,
    }


def upload_chat_media(file, file_type: str) -> str:
    """
    Upload media file (image, video, or voice) to GCS and return the public URL.

    Args:
        file: UploadFile object containing the media file
        file_type: Type of file - "image", "video", or "voice"

    Returns:
        str: Public GCS URL of the uploaded file

    Raises:
        ApiException: If file type is invalid or upload fails
    """
    # Map file type to bucket name
    bucket_mapping = {
        "image": "image-messages-bucket",
        "video": "video-messages-bucket",
        "voice": "voice-messages-url-bucket",
    }

    if file_type not in bucket_mapping:
        raise ApiException(
            status.HTTP_400_BAD_REQUEST,
            {
                "type": "invalid_file_type",
                "message": f"Invalid file type: {file_type}. Must be 'image', 'video', or 'voice'",
            },
        )

    bucket_name = bucket_mapping[file_type]

    try:
        # Create temporary file to store upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write uploaded file to temporary location
            temp_file.write(file.file.read())
            temp_file_path = temp_file.name

        # Generate unique filename with timestamp
        timestamp = datetime.utcnow().isoformat()
        original_filename = file.filename or f"{file_type}_message"
        destination_filename = f"{file_type}_messages_{timestamp}_{original_filename}"

        # Upload to GCS (make_public=True by default)
        file_url = storage_client.upload_to_bucket(
            bucket_name, temp_file_path, destination_filename
        )

        # Clean up temporary file
        os.remove(temp_file_path)

        logger.info(
            f"Successfully uploaded {file_type} file to GCS (public): {file_url}"
        )

        return file_url

    except Exception as e:
        # Clean up temporary file if it exists
        if "temp_file_path" in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        logger.error(f"Failed to upload {file_type} file to GCS: {str(e)}")
        raise ApiException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {
                "type": "upload_failed",
                "message": f"Failed to upload {file_type} file: {str(e)}",
            },
        )
