from fastapi import APIRouter, Depends, UploadFile, File, status, Header, Query, Body
from src.app.secrets.passwords import hash_password
from src.app.db.orm import get_db
from .modelsIn import NamespaceRegistry
from src.app.resourcesController import (
    users_controller,
    namespace_controller,
    guest_controller,
)
from src.app.globals.emails import send_email
from dotmap import DotMap
from src.settings import settings
from src.app.secrets.jwt import sign_jwt
from src.app.globals.schema_models import UsersModel, NamespaceModel, GuestModel
from src.app.db.models import Namespace
from sqlalchemy import and_, or_
from src.app.globals.exceptions import ApiException
from src.app.globals.error import Error
from src.app.globals.response import ApiResponse
from src.app.routers.auth.modelsOut import (
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
from src.app.globals.generic_responses import validation_response
from src.app.globals.authentication import domain_auth, CurrentUserIdentifier
from src.app.globals.generic_responses import (
    invalid_token_response,
    expired_token_response,
    not_authenticated_response,
    db_error_response,
)
from pydantic import EmailStr
from src.app.routers.auth.services import send_otp, generate_otp
from src.app.globals.error import dbError
from src.app.secrets.jwt import sign_jwt
from src.app.db.models import Stay, Claim, Users
from sqlalchemy import desc, func
from datetime import datetime
from src.app.globals.schema_models import ClaimStatus
from src.app.globals.schema_models import role_categ_assoc
from .services import detect_time_zone

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
    namespace["timezone"] = detect_time_zone(
        namespace_dict["country"], namespace_dict["city"]
    )
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

    app_user = guest_controller.find_by_id(phone_number)
    if not app_user:
        app_user = users_controller.find_by_field("phone_number", phone_number)

        if not app_user:
            raise ApiException(status.HTTP_404_NOT_FOUND, no_user_error)
        if push_token:
            users_controller.update(
                app_user["id"], dict(current_device_token=push_token)
            )

        return GuestLoginResponse(data=GuestLogin(token=sign_jwt(app_user)))
    if push_token:
        guest_controller.update(
            app_user["phone_number"],
            dict(current_device_token=push_token),
            resource_key="phone_number",
        )
    return GuestLoginResponse(data=GuestLogin(token=sign_jwt(app_user)))


@router.get("/get_otp", response_model=OtpResponse)
def get_otp(current_user: dict = Depends(CurrentUserIdentifier(who="any"))):
    push_token = current_user["current_device_token"]
    otp = send_otp(push_token)
    return OtpResponse(data=OtpModel(otp=otp))


@router.get("/me", response_model=MeResponse)
def me(
    current_guest: dict = Depends(CurrentUserIdentifier(who="any")),
    db=Depends(get_db),
) -> ApiResponse:

    if "id" not in current_guest:
        current_stay = (
            db.query(Stay)
            .filter(Stay.guest_id == current_guest["phone_number"])
            .order_by(desc(Stay.start_date))
            .first()
        )
        today = datetime.now()

        sejour = dict(stay=False)
        sejour["fullname"] = (
            f"{current_guest['first_name']} {current_guest['last_name']}"
        )

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

    if "id" in current_guest:
        user = db.query(Users).filter(Users.id == current_guest["id"]).first()
        namespace = (
            db.query(Namespace).filter(Namespace.id == user.namespace_id).first()
        )

        today = datetime.now().date()

        # Get allowed categories for user's role
        allowed_categories = role_categ_assoc.get(user.role, [])

        # Base query filtering by namespace, date and allowed categories
        base_claims_query = db.query(Claim).filter(
            Claim.namespace_id == user.namespace_id,
            func.date(Claim.created_at) == today,
            Claim.claim_category.in_(allowed_categories),
        )

        def get_claim_stats(claims_query, status: ClaimStatus):
            filtered_claims = claims_query.filter(Claim.status == status).all()
            count = len(filtered_claims)
            if count == 0:
                return {"count": 0, "avg_time": 0}

            total_time = 0
            for claim in filtered_claims:
                if status == ClaimStatus.processing:
                    # Time from creation to acknowledgment
                    if claim.acknowledged_claim_time:
                        total_time += (
                            datetime.now() - claim.acknowledged_claim_time
                        ).total_seconds()
                elif status == ClaimStatus.resolved:
                    # Time from acknowledgment to resolution
                    if claim.resolve_claim_time and claim.acknowledged_claim_time:
                        total_time += (
                            claim.resolve_claim_time - claim.acknowledged_claim_time
                        ).total_seconds()
                elif status == ClaimStatus.closed:
                    # Time from resolution to approval
                    if claim.approve_claim_time and claim.resolve_claim_time:
                        total_time += (
                            claim.approve_claim_time - claim.resolve_claim_time
                        ).total_seconds()
                elif status == ClaimStatus.pending:
                    # Time since creation for pending claims
                    total_time += (datetime.now() - claim.created_at).total_seconds()

            avg_time = total_time / count if count > 0 else 0
            return {"count": count, "avg_time": avg_time}

        claims_stats = {
            "pending": get_claim_stats(base_claims_query, ClaimStatus.pending),
            "processing": get_claim_stats(base_claims_query, ClaimStatus.processing),
            "resolved": get_claim_stats(base_claims_query, ClaimStatus.resolved),
            "closed": get_claim_stats(base_claims_query, ClaimStatus.closed),
            "rejected": {
                "count": base_claims_query.filter(
                    Claim.status == ClaimStatus.rejected
                ).count()
            },
        }

        user_data = {
            "fullname": f"{user.first_name} {user.last_name}",
            "company_name": namespace.hotel_name,
            "role": user.role,
            "avatar": user.avatar_url,
            "claims_stats": claims_stats,
        }

        return MeResponse(data=user_data)
