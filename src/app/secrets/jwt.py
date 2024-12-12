import jwt
from src.settings import settings
from time import time
from datetime import datetime
import jwt
from src.settings import settings
from src.app.globals.exceptions import ApiException
from fastapi import status
from src.app.globals.error import invalid_token, expired_token
from time import time


def sign_jwt(data: dict, expires=settings.jwt_access_expires) -> str:
    new_data = data.copy()
    for key, value in data.items():
        if isinstance(value, datetime):
            new_data.pop(key)
    payload = {"data": new_data, "expires": time() + expires}

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str):
    try:
        decoded_token = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except:
        raise ApiException(status.HTTP_401_UNAUTHORIZED, error=invalid_token)
    if "data" not in decoded_token or not decoded_token["data"]:
        raise ApiException(status.HTTP_401_UNAUTHORIZED, error=invalid_token)
    if decoded_token["expires"] < time():
        raise ApiException(status.HTTP_410_GONE, expired_token)
    return decoded_token["data"]
