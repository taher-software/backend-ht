from pydantic import BaseModel, Field
from typing import Optional


class PreferencesUpdateIn(BaseModel):
    pref_language: Optional[str] = Field(None)
    notifications_enabled: Optional[bool] = Field(None)


class PrefLangUpdateIn(BaseModel):
    pref_lang: str = Field(..., min_length=2, max_length=2)
