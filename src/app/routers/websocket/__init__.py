from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from src.app.db.orm import get_db
from .services import handle_websocket_message, cleanup_websocket_connections
from src.app.routers.chat.modelsIn import WebSocketMessageSchema
from src.app.secrets.jwt import decode_jwt
from src.app.globals.exceptions import ApiException
from src.app.resourcesController import users_controller, guest_controller
import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["WebSocket"])

guest_connections: dict[str, list] = defaultdict(list)
user_connections: dict[str, list] = defaultdict(list)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat messaging.

    The client must send a token in the query parameters or headers for authentication.
    Messages should comply with the WebSocketMessageSchema.
    """
    await websocket.accept()

    current_user = None
    room_id = None
    db = None
    guest_id = None
    user_id = None

    try:
        # Extract token from query parameters or headers
        token = websocket.query_params.get("token") or websocket.headers.get("token")

        if not token:
            await websocket.send_json(
                {"error": "Authentication required", "message": "No token provided"}
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Decode and validate token
        try:
            decoded_data = decode_jwt(token)
        except Exception as e:
            logger.error(f"Token decoding failed: {str(e)}")
            await websocket.send_json(
                {"error": "Invalid token", "message": "Token is invalid or expired"}
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Identify user type (user or guest)
        if "id" in decoded_data:
            # It's a user
            user = users_controller.find_by_id(decoded_data["id"])
            if not user:
                await websocket.send_json(
                    {
                        "error": "User not found",
                        "message": "Authenticated user does not exist",
                    }
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            current_user = decoded_data
            user_connections[decoded_data["id"]].append(websocket)
            user_id = decoded_data["id"]
        elif "phone_number" in decoded_data:
            # It's a guest
            guest = guest_controller.find_by_field(
                "phone_number", decoded_data["phone_number"]
            )
            if not guest:
                await websocket.send_json(
                    {
                        "error": "Guest not found",
                        "message": "Authenticated guest does not exist",
                    }
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            current_user = decoded_data
            guest_connections[decoded_data["phone_number"]].append(websocket)
            guest_id = decoded_data["phone_number"]
        else:
            await websocket.send_json(
                {
                    "error": "Invalid token",
                    "message": "Token does not contain valid user information",
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        logger.info(f"WebSocket connection authenticated for user: {current_user}")

        # Listen for messages
        while True:
            # Receive data from WebSocket
            data = await websocket.receive_text()

            try:
                # Parse JSON data
                message_data = json.loads(data)

                # Validate data against schema
                validated_message = WebSocketMessageSchema(**message_data)

                # Handle message event
                room_id = validated_message.room_id

                # Get database session
                db = next(get_db())

                try:
                    # Process the message
                    message_handling_response = handle_websocket_message(
                        room_id=room_id,
                        current_user=current_user,
                        message_type=validated_message.message_type,
                        text=validated_message.text,
                        image_url=validated_message.image_url,
                        video_url=validated_message.video_url,
                        voice_url=validated_message.voice_url,
                        duration=validated_message.duration,
                        user_connections=user_connections,
                        guest_connections=guest_connections,
                    )

                    message = message_handling_response["message"]
                    connections = message_handling_response["connections"]

                    # Broadcast message to all connections in the room
                    if connections and len(connections) > 0:
                        for connection in connections:
                            await connection.send_json(message)

                except ApiException as e:
                    await websocket.send_json(
                        {
                            "error": (
                                e.error.type if hasattr(e.error, "type") else "error"
                            ),
                            "message": (
                                e.error.message
                                if hasattr(e.error, "message")
                                else str(e.error)
                            ),
                        }
                    )
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    await websocket.send_json(
                        {
                            "error": "internal_error",
                            "message": f"Failed to process message: {str(e)}",
                        }
                    )
                finally:
                    if db:
                        db.close()

            except json.JSONDecodeError:
                await websocket.send_json(
                    {"error": "invalid_json", "message": "Message must be valid JSON"}
                )
            except Exception as e:
                logger.error(f"Validation error: {str(e)}")
                await websocket.send_json(
                    {"error": "validation_error", "message": str(e)}
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for room_id: {room_id}")
        # Clean up connections
        cleanup_websocket_connections(
            websocket, guest_id, user_id, guest_connections, user_connections
        )

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({"error": "internal_error", "message": str(e)})
        except:
            pass

    finally:
        # Clean up guest/user connections
        cleanup_websocket_connections(
            websocket, guest_id, user_id, guest_connections, user_connections
        )

        # Clean up database session if still open
        if db:
            db.close()
