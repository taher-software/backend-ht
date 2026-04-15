from fastapi import APIRouter, Depends, Query, HTTPException
from src.app.globals.generic_responses import validation_response
from src.app.globals.response import ApiResponse
from src.app.globals.authentication import CurrentUserIdentifier
from src.app.globals.schema_models import Role, ClaimCategory
from src.app.db.orm import get_db
from typing import Literal
from .services import (
    get_kpi_stars_rooms,
    get_kpi_stars_room_check_in,
    get_kpi_stars_restaurants,
    get_kpi_stars_dishes,
    get_housekeepers_performance,
    get_claims_handling_performance,
    get_dishes_score,
    get_queue_root_cause,
    get_kpi_stars_rooms_range,
    get_kpi_stars_room_check_in_range,
    get_kpi_stars_restaurants_range,
    get_rooms_kpi_evolution,
    get_restaurants_kpi_evolution,
    get_claim_kpi_evolution,
    get_claims_response_time_evolution,
    get_rooms_check_in_kpi_evolution,
    get_average_claims_response_time,
    get_claims_per_category,
)

ROOMS_STATS_ALLOWED_ROLES = {
    Role.owner.value,
    Role.admin.value,
    Role.supervisor.value,
    Role.housekeeping_supervisor.value,
}

CHECK_IN_STATS_ALLOWED_ROLES = {
    Role.owner.value,
    Role.admin.value,
    Role.supervisor.value,
    Role.guest_relations_supervisor.value,
    Role.housekeeping_supervisor.value,
}

RESTAURANTS_STATS_ALLOWED_ROLES = {
    Role.owner.value,
    Role.admin.value,
    Role.supervisor.value,
    Role.dining_supervisor.value,
}

router = APIRouter(prefix="/stats", tags=["Stats"], responses={**validation_response})


@router.get("/kpi_stars_rooms")
def kpi_stars_rooms(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    room_id: str | None = Query(None),
    housekeeper_id: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & ROOMS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    averages = get_kpi_stars_rooms(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        room_id=room_id,
        housekeeper_id=housekeeper_id,
    )
    return ApiResponse(data=averages)


@router.get("/kpi_stars_room_check_in")
def kpi_stars_room_check_in(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    room_id: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & CHECK_IN_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    averages = get_kpi_stars_room_check_in(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        room_id=room_id,
    )
    return ApiResponse(data=averages)


@router.get("/kpi_stars_restaurants")
def kpi_stars_restaurants(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & RESTAURANTS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    averages = get_kpi_stars_restaurants(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=averages)


@router.get("/kpi_stars_dishes")
def kpi_stars_dishes(
    stat_date: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & RESTAURANTS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_kpi_stars_dishes(
        db=db,
        namespace_id=current_user["namespace_id"],
        stat_date=stat_date,
    )
    return ApiResponse(data=result)


@router.get("/housekeepers_performance")
def housekeepers_performance(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    housekeeper_id: str | None = Query(None),
    room_id: str | None = Query(None),
    global_view: bool = Query(False, alias="global"),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & ROOMS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_housekeepers_performance(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        housekeeper_id=housekeeper_id,
        room_id=room_id,
        global_view=global_view,
    )
    return ApiResponse(data=result)


@router.get("/claims_handling_performance")
def claims_handling_performance(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    claim_category: ClaimCategory | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    result = get_claims_handling_performance(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        claim_category=claim_category,
    )
    return ApiResponse(data=result)


@router.get("/dishes_score")
def dishes_score(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    variant: Literal["best", "worst"] | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & RESTAURANTS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_dishes_score(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        variant=variant,
    )
    return ApiResponse(data=result)


@router.get("/queue_root_cause")
def queue_root_cause(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & RESTAURANTS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_queue_root_cause(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=result)


@router.get("/kpi_stars_rooms_range")
def kpi_stars_rooms_range(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    room_id: str | None = Query(None),
    housekeeper_id: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & ROOMS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_kpi_stars_rooms_range(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        room_id=room_id,
        housekeeper_id=housekeeper_id,
    )
    return ApiResponse(data=result)


@router.get("/kpi_stars_room_check_in_range")
def kpi_stars_room_check_in_range(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    room_id: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & CHECK_IN_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_kpi_stars_room_check_in_range(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        room_id=room_id,
    )
    return ApiResponse(data=result)


@router.get("/rooms_kpi_evolution")
def rooms_kpi_evolution(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    room_id: str | None = Query(None),
    housekeeper_id: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & ROOMS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_rooms_kpi_evolution(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        room_id=room_id,
        housekeeper_id=housekeeper_id,
    )
    return ApiResponse(data=result)


@router.get("/rooms_check_in_kpi_evolution")
def rooms_check_in_kpi_evolution(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    room_id: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & CHECK_IN_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_rooms_check_in_kpi_evolution(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        room_id=room_id,
    )
    return ApiResponse(data=result)


@router.get("/claims_per_category")
def claims_per_category(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    result = get_claims_per_category(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=result)


@router.get("/average_claims_response_time")
def average_claims_response_time(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    claim_category: ClaimCategory | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    result = get_average_claims_response_time(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        claim_category=claim_category,
    )
    return ApiResponse(data=result)


@router.get("/claims_response_time_evolution")
def claims_response_time_evolution(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    claim_category: ClaimCategory | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    result = get_claims_response_time_evolution(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        claim_category=claim_category,
    )
    return ApiResponse(data=result)


@router.get("/claim_kpi_evolution")
def claim_kpi_evolution(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    claim_category: ClaimCategory | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    result = get_claim_kpi_evolution(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
        claim_category=claim_category,
    )
    return ApiResponse(data=result)


@router.get("/restaurants_kpi_evolution")
def restaurants_kpi_evolution(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & RESTAURANTS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_restaurants_kpi_evolution(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=result)


@router.get("/kpi_stars_restaurants_range")
def kpi_stars_restaurants_range(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict = Depends(CurrentUserIdentifier(who="user")),
    db=Depends(get_db),
) -> ApiResponse:
    if not set(current_user.get("role", [])) & RESTAURANTS_STATS_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    result = get_kpi_stars_restaurants_range(
        db=db,
        namespace_id=current_user["namespace_id"],
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=result)
