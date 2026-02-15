from pydantic import BaseModel, Field
from typing import Literal, Optional


class WebSocketMessageSchema(BaseModel):
    """
    Schema for WebSocket messages in the chat system.
    """

    room_id: int = Field(..., description="ID of the chat room")
    message_type: Literal["image", "audio", "video", "text"] = Field(
        ..., description="Type of message content"
    )
    text: Optional[str] = Field(None, description="Text content of the message")
    image_url: Optional[str] = Field(None, description="URL of the image")
    video_url: Optional[str] = Field(None, description="URL of the video")
    voice_url: Optional[str] = Field(None, description="URL of the voice/audio")
    duration: Optional[float] = Field(
        None, description="Duration of voice/audio message in seconds"
    )
