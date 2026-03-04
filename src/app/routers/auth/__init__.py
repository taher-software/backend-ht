from fastapi import APIRouter, Depends, UploadFile, File, status, Header, Query, Body
from src.app.db.orm import get_db
from .modelsIn import NamespaceRegistry, WebAppLogin
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
    invalid_credentials_response,
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
from src.app.db.models import Stay, Claim, Users, Meal
from sqlalchemy import desc, func
from datetime import datetime
from src.app.globals.schema_models import ClaimStatus
from src.app.globals.schema_models import role_categ_assoc
from .services import detect_time_zone
from .services import count_current_survey
from .services import handle_register_new_domain
from .services import handle_web_app_login
from src.app.db.models.namespace_settings import NamespaceSettings
from src.app.globals.utils import (
    breakfast_eligible_plans,
    lunch_eligible_plans,
    dinner_eligible_plans,
)
from src.app.globals.enum import MealEnum

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

    return handle_register_new_domain(payload, avatar)


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
    "/web_app_login",
    response_model=GuestLoginResponse,
    description="API for web app login with username and password",
    responses={**invalid_credentials_response},
)
def web_app_login(
    payload: WebAppLogin,
    db=Depends(get_db),
) -> ApiResponse:
    result = handle_web_app_login(payload.username, payload.password, db)
    return GuestLoginResponse(data=GuestLogin(token=result["token"]))


@router.post(
    "/mobile_login",
    description="API for sign in guest to mobile app",
    response_model=GuestLoginResponse,
    responses={**no_guest_response},
)
def mobile_login(
    phone_number: str = Body(..., pattern="^\+?[1-9]\d{1,14}$"),
    push_token: str | None = Body(None),
    db=Depends(get_db),
) -> ApiResponse:

    app_user = guest_controller.find_by_id(phone_number)
    if not app_user:
        app_user = users_controller.find_by_field("phone_number", phone_number)

        if not app_user:
            raise ApiException(status.HTTP_404_NOT_FOUND, no_user_error)
        if push_token:
            users_controller.update(
                app_user["id"], dict(current_device_token=push_token), db=db
            )

        return GuestLoginResponse(data=GuestLogin(token=sign_jwt(app_user)))
    if push_token:
        guest_controller.update(
            app_user["phone_number"],
            dict(current_device_token=push_token),
            resource_key="phone_number",
            db=db,
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
        today = datetime.now().date()

        sejour = dict(stay=False)
        sejour["fullname"] = (
            f"{current_guest['first_name']} {current_guest['last_name']}"
        )

        sejour["avatar"] = current_guest["avatar_url"]
        sejour["phone_number"] = current_guest["phone_number"]

        if not current_stay:
            stay_model = StayModel(**sejour)
            return MeResponse(data=stay_model)
        if today >= current_stay.start_date and today <= current_stay.end_date:

            meal_plan = current_stay.meal_plan
            sejour["stay"] = True
            namespace = namespace_controller.find_by_id(current_stay.namespace_id)
            sejour["hotel_name"] = namespace["hotel_name"]
            sejour["country"] = namespace["country"]

            claim_count = len(
                db.query(Claim).filter(Claim.stay_id == current_stay.id).all()
            )

            ns_settings = (
                db.query(NamespaceSettings)
                .filter(NamespaceSettings.namespace_id == current_stay.namespace_id)
                .first()
            )
            menu_count = 0
            if ns_settings:
                now = datetime.now().time()
                today = datetime.now().date()
                today_meal_types = {
                    meal.meal_type
                    for meal in db.query(Meal).filter(
                        Meal.namespace_id == current_stay.namespace_id,
                        Meal.meal_date == today,
                    ).all()
                }
                if (
                    (
                        (
                            ns_settings.breakfast_menu_time
                            <= now
                            <= ns_settings.breakfast_end_time
                        )
                        and (meal_plan in breakfast_eligible_plans)
                        and (MealEnum.BREAKFAST in today_meal_types)
                    )
                    or (
                        (
                            ns_settings.lunch_menu_time
                            <= now
                            <= ns_settings.lunch_end_time
                        )
                        and (meal_plan in lunch_eligible_plans)
                        and (MealEnum.LUNCH in today_meal_types)
                    )
                    or (
                        (
                            ns_settings.dinner_menu_time
                            <= now
                            <= ns_settings.dinner_end_time
                        )
                        and (meal_plan in dinner_eligible_plans)
                        and (MealEnum.DINNER in today_meal_types)
                    )
                ):
                    menu_count = 1
            sejour["menu_count"] = menu_count
            sejour["claim_count"] = claim_count
            sejour["survey_count"] = count_current_survey(
                db, current_stay.namespace_id, current_guest["phone_number"]
            )
            sejour["pref_language"] = current_guest["pref_language"]

        stay_model = StayModel(**sejour)
        return MeResponse(data=stay_model)

    if "id" in current_guest:
        user = db.query(Users).filter(Users.id == current_guest["id"]).first()
        namespace = (
            db.query(Namespace).filter(Namespace.id == user.namespace_id).first()
        )

        today = datetime.now().date()

        # Get allowed categories for user's roles
        allowed_categories = []
        for role in user.role:
            categories = role_categ_assoc.get(role, [])
            allowed_categories.extend(categories)
        # Remove duplicates
        allowed_categories = list(set(allowed_categories))

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
            "namespace_id": namespace.id,
            "role": user.role,
            "avatar": user.avatar_url,
            "claims_stats": claims_stats,
            "phone_number": user.phone_number if user.phone_number else "",
            "pref_language": user.pref_language if user.pref_language else None
        }
            
        return MeResponse(data=user_data)
