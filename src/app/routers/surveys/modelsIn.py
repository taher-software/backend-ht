from pydantic import BaseModel, conlist, conint
from src.app.globals.enum import Survey
from typing import List, Any, Dict


class SubmitSurveyPayload(BaseModel):
    survey_type: Survey
    responses: conlist(conint(ge=0, le=5), min_length=4, max_length=5)


class DishesSurveySubmitPayload(BaseModel):
    responses: Dict[str, float]  # dish_id: score
