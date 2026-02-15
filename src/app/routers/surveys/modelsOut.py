from pydantic import BaseModel
from typing import List, Any
from src.app.globals.enum import Survey


class SurveyResponse(BaseModel):
    """Model for survey response data"""

    survey_type: Survey
    survey_questions: List[str]
    queue_factors: List[str] | None = None
    breakfast_questions: str | None = None
    lunch_questions: str | None = None
    dinner_questions: str | None = None
    dish_question: str | None = None
    breakfast_dishes: List[dict[str, Any]] | None = None
    lunch_dishes: List[dict[str, Any]] | None = None
    dinner_dishes: List[dict[str, Any]] | None = None
