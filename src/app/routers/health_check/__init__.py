from fastapi import APIRouter
from src.app.globals.generic_responses import validation_response

router = APIRouter(
    prefix="/health", tags=["Health_Check"], responses={**validation_response}
)


@router.get("/")
def health_check():
    import ipdb

    ipdb.set_trace()
    return "Runing up and well!"
