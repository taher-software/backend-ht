from enum import Enum


class Status(str, Enum):
    success: str = "success"
    failed: str = "failed"
