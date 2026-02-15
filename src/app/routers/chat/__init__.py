from fastapi import (
    APIRouter,
    Depends,
    Query,
    UploadFile,
    File,
)
from src.app.db.orm import get_db
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from .modelsOut import (
    claim_not_found_response,
    guest_not_found_response,
    namespace_mismatch_response,
    stay_not_found_response,
    invalid_stay_dates_response,
    stay_namespace_mismatch_response,
    no_device_token_response,
    notification_failed_response,
)
from .services import (
    handle_initialize_chat,
    get_chat_rooms,
    get_chat_room_messages,
    upload_chat_media,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"], responses={**validation_response})


@router.post(
    "/initialize_chat",
    response_model=ApiResponse,
    description="Initialize a chat room for a specific claim (user only)",
    responses={
        **claim_not_found_response,
        **guest_not_found_response,
        **namespace_mismatch_response,
        **stay_not_found_response,
        **invalid_stay_dates_response,
        **stay_namespace_mismatch_response,
        **no_device_token_response,
        **notification_failed_response,
    },
)
def initialize_chat(
    claim_id: int = Query(..., description="ID of the claim"),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
) -> ApiResponse:
    result = handle_initialize_chat(claim_id, current_user)
    return ApiResponse(data=result)


@router.get(
    "/rooms",
    response_model=ApiResponse,
    description="Get list of active chat rooms for current user or guest",
)
def list_chat_rooms(
    current_user: dict = Depends(CurrentUserIdentifier(who="any")),
    db=Depends(get_db),
) -> ApiResponse:
    """
    Get list of active chat rooms.

    For users: Returns all active chat rooms where the user is involved.
    For guests: First checks if guest has an active stay, then returns chat rooms for that stay.

    Returns chat rooms sorted by created_at descending, with stay and room information loaded.
    """
    result = get_chat_rooms(current_user, db)
    return ApiResponse(data=result)


@router.get(
    "/chat_room_messages/{chat_room_id}",
    response_model=ApiResponse,
    description="Get all messages for a specific chat room",
)
def list_chat_room_messages(
    chat_room_id: int,
    current_user: dict = Depends(CurrentUserIdentifier(who="any")),
    db=Depends(get_db),
) -> ApiResponse:
    """
    Get all messages for a specific chat room.

    Validates that the current user (user or guest) belongs to the chat room.
    Returns messages sorted by created_at ascending.
    """
    result = get_chat_room_messages(chat_room_id, current_user, db)
    return ApiResponse(data=result)


@router.post(
    "/upload_media",
    response_model=ApiResponse,
    description="Upload media file (image, video, or voice) for chat messages",
)
def upload_media_file(
    file: UploadFile = File(..., description="Media file to upload"),
    file_type: str = Query(
        ..., description="Type of file: 'image', 'video', or 'voice'"
    ),
    current_user: dict = Depends(CurrentUserIdentifier(who="any")),
) -> ApiResponse:
    """
    Upload media file to GCS and return the URL.

    Accepts image, video, or voice files and uploads them to the appropriate GCS bucket.
    Returns the GCS URL of the uploaded file.

    Query parameter 'file_type' must be one of: 'image', 'video', or 'voice'
    """
    file_url = upload_chat_media(file, file_type)
    return ApiResponse(data={"url": file_url, "file_type": file_type})
