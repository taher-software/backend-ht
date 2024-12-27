from fastapi import APIRouter, Depends, UploadFile, File, status, Header, Query, Body
from app.secrets.passwords import hash_password
from app.db.orm import get_db
from .modelsIn import NamespaceRegistry
from app.resourcesController import (
    users_controller,
    namespace_controller,
    guest_controller,
)
from app.globals.emails import send_email
from dotmap import DotMap
from settings import settings
from app.secrets.jwt import sign_jwt
from app.globals.schema_models import UsersModel, NamespaceModel, GuestModel
from app.db.models import Namespace
from sqlalchemy import and_, or_
from app.globals.exceptions import ApiException
from app.globals.error import Error
from app.globals.response import ApiResponse
from app.routers.auth.modelsOut import (
    MessageResponse,
    no_domain_error,
    no_domain_response,
    no_user_error,
    no_guest_response,
    hotel_exist_error,
    hotel_existe_response,
    GuestLoginResponse,
    GuestLogin,
    AppUser,
    OtpResponse,
    OtpModel,
    MeResponse,
    StayModel,
)
from app.globals.generic_responses import validation_response
from app.globals.authentication import domain_auth, CurrentUserIdentifier
from app.globals.generic_responses import (
    invalid_token_response,
    expired_token_response,
    not_authenticated_response,
    db_error_response,
)
from pydantic import EmailStr
from app.routers.auth.services import send_otp, generate_otp
from app.globals.error import dbError
from app.secrets.jwt import sign_jwt
from app.db.models import Stay, Claim
from sqlalchemy import desc
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Auth"], responses={**validation_response})


@router.post(
    "/register",
    response_model=MessageResponse,
    description="API for registering new domain",
    responses={**db_error_response, **hotel_existe_response},
)
async def register_new_domain(
    payload: NamespaceRegistry, avatar: UploadFile = File(None), db=Depends(get_db)
) -> ApiResponse:

    payload_dict = dict(payload)
    payload_map = DotMap(payload_dict)

    check_hotel = (
        db.query(Namespace)
        .filter(
            or_(
                Namespace.business_registration_number
                == payload_map.business_registration_number,
                Namespace.tax_identification_number
                == payload_map.tax_identification_number,
                and_(
                    Namespace.hotel_name == payload_map.hotel_name,
                    Namespace.country == payload_map.country,
                ),
            )
        )
        .first()
    )
    if check_hotel:
        raise ApiException(
            status_code=status.HTTP_409_CONFLICT, error=hotel_exist_error
        )
    user_dict = dict(UsersModel(**payload_dict))
    user_dict["hashed_password"] = hash_password(payload_dict.pop("password"))
    user_dict["avatar_url"] = "https://avatars.githubusercontent.com/u/85107514?v=4"
    namespace_dict = dict(NamespaceModel(**payload_dict))
    namespace_dict["hotel_website_url"] = str(namespace_dict.pop("hotel_website_url"))
    namespace_controller.create(namespace_dict)
    namespace = (
        db.query(Namespace)
        .filter(
            and_(
                Namespace.country == payload_map.country,
                Namespace.hotel_name == payload_map.hotel_name,
            )
        )
        .first()
    )
    namespace_id = namespace.id
    user_dict["namespace_id"] = namespace_id
    try:
        users_controller.create(user_dict)
    except Exception as e:
        namespace_controller.delete(namespace_id)
        raise ApiException(status.HTTP_406_NOT_ACCEPTABLE, dbError(detail=str(e)))

    owner_row = users_controller.find_by_field("user_email", payload_map.user_email)
    verification_link = f"{settings.application_url}{sign_jwt(owner_row)}"
    send_email(
        payload_map.user_email,
        payload_map.first_name,
        verification_link,
    )

    return MessageResponse(data="New domain registred successfully!")


@router.post(
    "/email_confirmation",
    response_model=MessageResponse,
    description="API to confirm emails",
    responses={
        **invalid_token_response,
        **expired_token_response,
        **not_authenticated_response,
        **no_domain_response,
    },
)
def email_confirmation(token_registry: str = Header(...), da=Depends(domain_auth())):
    return MessageResponse(data="new Domain was succesfully confirmed!")


@router.get(
    "/resend_email",
    response_model=MessageResponse,
    description="API for resending email confirmation!",
    responses={**no_domain_response},
)
def resend_email_confirmation(user_email: EmailStr = Query):
    owner_row = users_controller.find_by_field("user_email", user_email)
    if not owner_row:
        raise ApiException(
            status.HTTP_417_EXPECTATION_FAILED,
            no_domain_error,
        )
    verification_link = f"{settings.application_url}{sign_jwt(owner_row)}"
    owner_row = DotMap(owner_row)
    send_email(
        user_email,
        owner_row.first_name,
        verification_link,
    )
    return MessageResponse(data="Email confirmation resended successfully!")


@router.post(
    "/mobile_login",
    description="API for sign in guest to mobile app",
    response_model=GuestLoginResponse,
    responses={**no_guest_response},
)
def mobile_login(
    phone_number: str = Body(..., pattern="^\+?[1-9]\d{1,14}$"),
    push_token: str | None = Body(None),
) -> ApiResponse:
    print(f"push_token_mobile_login: {push_token}")
    app_user = guest_controller.find_by_id(phone_number)
    if not app_user:
        app_user = users_controller.find_by_field("phone_number", phone_number)

        if not app_user:
            raise ApiException(status.HTTP_404_NOT_FOUND, no_user_error)
        users_controller.update(app_user["id"], dict(current_device_token=push_token))

        return GuestLoginResponse(data=GuestLogin(token=sign_jwt(app_user)))
    if push_token:
        guest_controller.update(
            app_user["phone_number"],
            dict(current_device_token=push_token),
            resource_key="phone_number",
        )
    return GuestLoginResponse(data=GuestLogin(token=sign_jwt(app_user)))


@router.get("/get_otp", response_model=OtpResponse)
def get_otp(current_guest: dict = Depends(CurrentUserIdentifier())):
    push_token = current_guest["current_device_token"]
    otp = send_otp(push_token)
    return OtpResponse(data=OtpModel(otp=otp))


@router.get("/me", response_model=MeResponse)
def me(
    current_guest: dict = Depends(CurrentUserIdentifier()), db=Depends(get_db)
) -> ApiResponse:

    current_stay = (
        db.query(Stay)
        .filter(Stay.guest_id == current_guest["phone_number"])
        .order_by(desc(Stay.start_date))
        .first()
    )
    today = datetime.now()

    sejour = dict(stay=False)
    sejour["fullname"] = f"{current_guest['first_name']} {current_guest['last_name']}"

    sejour["avatar"] = current_guest["avatar_url"]
    if not current_stay:
        stay_model = StayModel(**sejour)
        return MeResponse(data=stay_model)
    if today >= current_stay.start_date and today <= current_stay.end_date:

        sejour["stay"] = True
        namespace = namespace_controller.find_by_id(current_stay.namespace_id)
        sejour["hotel_name"] = namespace["hotel_name"]
        sejour["hotel_name"] = namespace["hotel_name"]
        sejour["country"] = namespace["country"]

        claim_count = len(
            db.query(Claim).filter(Claim.stay_id == current_stay.id).all()
        )
        survey_count = 1  # it should be computed whenever survey is added
        menu_count = 1  # it should be computed whenever menu is added
        sejour["claim_count"] = claim_count
        sejour["survey_count"] = survey_count
        sejour["menu_count"] = menu_count

    stay_model = StayModel(**sejour)
    return MeResponse(data=stay_model)
