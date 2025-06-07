from fastapi import FastAPI, status, Request
from starlette.middleware.cors import CORSMiddleware
from src.app.db.orm import Base, engine
from src.app.db import models
from src.app.routers import add_routers
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from src.app.globals.exceptions import ApiException
from src.app.globals.error import Error
from fastapi.responses import JSONResponse
from starlette.concurrency import iterate_in_threadpool
from src.app.globals.response import ApiResponse


def create_tables():
    Base.metadata.create_all(bind=engine)


def start_app():

    app = FastAPI(
        docs_url="/",
        title="Bodor app backend apis",
        description="""### API for Bodor app
        ### Notes:
        * APIs require IAP Authentication`.
        * All the api responses are in application/json format.
        """,
        version="1.0",
    )

    # add_routers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_, exc: RequestValidationError):
        err = jsonable_encoder({"detail": exc.errors()})["detail"]
        raise ApiException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error=Error(
                type="Validation", message="validation_error", detail=err[0]["msg"]
            ),
        )

    @app.middleware("http")
    async def middle(request: Request, call_next):
        """Wrapper function to manage errors"""
        if request.url._url.endswith("/") or request.url._url.endswith("/openapi.json"):
            return await call_next(request)

        try:
            response = await call_next(request)
            raw_response = [section async for section in response.body_iterator]
            response.body_iterator = iterate_in_threadpool(iter(raw_response))
        except ApiException as ex:
            response = JSONResponse(
                status_code=ex.status_code,
                content=jsonable_encoder(ApiResponse(status="failed", error=ex.error)),
            )
        return response

    create_tables()
    add_routers(app)
    return app
