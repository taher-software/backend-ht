from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from src.app.db.models.daily_room_sat_survey import DailyRoomSatisfactionSurvey
from src.app.db.models.room_reception_survey import RoomReceptionSurvey
from src.app.db.models.daily_restaurant_survey import DailyRestaurantSurvey
from src.app.db.models.dishes_survey import DishesSurvey
from src.app.db.models.claims import Claim
from src.app.db.models.housekeepers import Housekeeper
from src.app.db.models.housekeeper_assignment import HousekeeperAssignment
from src.app.globals.schema_models import ClaimCategory, ClaimStatus


def resolve_date_range(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime, datetime]:
    if start_date and end_date:
        date_from = datetime.strptime(start_date, "%Y-%m-%d")
        date_to = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    else:
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        date_from = datetime.combine(yesterday, datetime.min.time())
        date_to = datetime.combine(yesterday, datetime.max.time())
    return date_from, date_to


def get_kpi_stars_rooms(
    db: Session,
    namespace_id: int,
    start_date: str | None,
    end_date: str | None,
    room_id: str | None,
    housekeeper_id: str | None,
) -> list[float | None]:
    date_from, date_to = resolve_date_range(start_date, end_date)

    filters = [
        DailyRoomSatisfactionSurvey.namespace_id == namespace_id,
        DailyRoomSatisfactionSurvey.created_at >= date_from,
        DailyRoomSatisfactionSurvey.created_at <= date_to,
    ]

    if room_id is not None:
        filters.append(DailyRoomSatisfactionSurvey.room_id == room_id)

    if housekeeper_id is not None:
        filters.append(DailyRoomSatisfactionSurvey.housekeeper_id == housekeeper_id)

    result = db.query(
        func.avg(DailyRoomSatisfactionSurvey.Q1),
        func.avg(DailyRoomSatisfactionSurvey.Q2),
        func.avg(DailyRoomSatisfactionSurvey.Q3),
        func.avg(DailyRoomSatisfactionSurvey.Q4),
    ).filter(and_(*filters)).one()

    return [round(v, 2) if v is not None else None for v in result]


def get_kpi_stars_room_check_in(
    db: Session,
    namespace_id: int,
    start_date: str | None,
    end_date: str | None,
    room_id: str | None,
) -> list[float | None]:
    date_from, date_to = resolve_date_range(start_date, end_date)

    filters = [
        RoomReceptionSurvey.namespace_id == namespace_id,
        RoomReceptionSurvey.created_at >= date_from,
        RoomReceptionSurvey.created_at <= date_to,
    ]

    if room_id is not None:
        filters.append(RoomReceptionSurvey.room_id == room_id)

    result = db.query(
        func.avg(RoomReceptionSurvey.Q1),
        func.avg(RoomReceptionSurvey.Q2),
        func.avg(RoomReceptionSurvey.Q3),
        func.avg(RoomReceptionSurvey.Q4),
    ).filter(and_(*filters)).one()

    return [round(v, 2) if v is not None else None for v in result]


def get_kpi_stars_restaurants(
    db: Session,
    namespace_id: int,
    start_date: str | None,
    end_date: str | None,
) -> list[float | None]:
    date_from, date_to = resolve_date_range(start_date, end_date)

    filters = [
        DailyRestaurantSurvey.namespace_id == namespace_id,
        DailyRestaurantSurvey.created_at >= date_from,
        DailyRestaurantSurvey.created_at <= date_to,
    ]

    result = db.query(
        func.avg(DailyRestaurantSurvey.Q1),
        func.avg(DailyRestaurantSurvey.Q2),
        func.avg(DailyRestaurantSurvey.Q3),
        func.avg(DailyRestaurantSurvey.Q4),
    ).filter(and_(*filters)).one()

    return [round(v, 2) if v is not None else None for v in result]


def get_housekeepers_performance(
    db: Session,
    namespace_id: int,
    start_date: str | None,
    end_date: str | None,
    housekeeper_id: str | None,
    room_id: str | None,
    global_view: bool = False,
) -> float | None | list[dict]:
    date_from, date_to = resolve_date_range(start_date, end_date)

    if not global_view:
        return get_housekeepers_performance_details(
            db=db,
            namespace_id=namespace_id,
            date_from=date_from,
            date_to=date_to,
            housekeeper_id=housekeeper_id,
            room_id=room_id,
        )

    filters = [
        DailyRoomSatisfactionSurvey.namespace_id == namespace_id,
        DailyRoomSatisfactionSurvey.created_at >= date_from,
        DailyRoomSatisfactionSurvey.created_at <= date_to,
    ]

    if housekeeper_id is not None:
        filters.append(DailyRoomSatisfactionSurvey.housekeeper_id == housekeeper_id)

    if room_id is not None:
        filters.append(DailyRoomSatisfactionSurvey.room_id == room_id)

    result = db.query(
        func.avg(DailyRoomSatisfactionSurvey.Q4)
    ).filter(and_(*filters)).scalar()

    return round(result, 2) if result is not None else None


def get_claims_handling_performance(
    db: Session,
    namespace_id: int,
    start_date: str | None,
    end_date: str | None,
    claim_category: ClaimCategory | None,
) -> dict[str, int]:
    date_from, date_to = resolve_date_range(start_date, end_date)

    base_filters = [
        Claim.namespace_id == namespace_id,
        Claim.created_at >= date_from,
        Claim.created_at <= date_to,
    ]

    if claim_category is not None:
        base_filters.append(Claim.claim_category == claim_category.value)

    def count_with(extra_filters: list) -> int:
        return db.query(func.count(Claim.id)).filter(and_(*base_filters, *extra_filters)).scalar() or 0

    resolved_statuses = [ClaimStatus.resolved.value, ClaimStatus.closed.value, ClaimStatus.rejected.value]

    return {
        "app.claims.received": count_with([]),
        "app.claims.resolved": count_with([Claim.status.in_(resolved_statuses)]),
        "app.claims.unclosed": count_with([Claim.status == ClaimStatus.resolved.value]),
        "app.claims.unresolved": count_with([Claim.status.in_([ClaimStatus.pending.value, ClaimStatus.processing.value])]),
        "app.claims.rejected": count_with([Claim.status == ClaimStatus.rejected.value]),
    }


def get_housekeepers_performance_details(
    db: Session,
    namespace_id: int,
    date_from: datetime,
    date_to: datetime,
    housekeeper_id: str | None,
    room_id: str | None,
) -> list[dict]:
    survey_filters = [
        DailyRoomSatisfactionSurvey.namespace_id == namespace_id,
        DailyRoomSatisfactionSurvey.created_at >= date_from,
        DailyRoomSatisfactionSurvey.created_at <= date_to,
    ]
    if room_id is not None:
        survey_filters.append(DailyRoomSatisfactionSurvey.room_id == room_id)
    if housekeeper_id is not None:
        survey_filters.append(
            DailyRoomSatisfactionSurvey.housekeeper_id == housekeeper_id
        )

    scored_rows = (
        db.query(
            DailyRoomSatisfactionSurvey.housekeeper_id,
            func.avg(DailyRoomSatisfactionSurvey.Q4),
        )
        .filter(and_(*survey_filters))
        .group_by(DailyRoomSatisfactionSurvey.housekeeper_id)
        .all()
    )

    result: list[dict] = []
    scored_ids: set[int] = set()

    for hk_id, avg_q4 in scored_rows:
        if hk_id is None:
            continue
        hk = db.query(Housekeeper).filter(Housekeeper.id == hk_id).first()
        if hk is None:
            continue
        scored_ids.add(hk_id)
        result.append(
            {
                "id": hk.id,
                "fullname": f"{hk.first_name} {hk.last_name}",
                "photoUrl": hk.avatar_url,
                "score": round(avg_q4, 2) if avg_q4 is not None else None,
            }
        )

    if housekeeper_id is None:
        assignment_filters = [
            HousekeeperAssignment.namespace_id == namespace_id,
            HousekeeperAssignment.date >= date_from.date(),
            HousekeeperAssignment.date <= date_to.date(),
        ]
        if room_id is not None:
            assignment_filters.append(
                HousekeeperAssignment.room_id == room_id
            )

        assigned_rows = (
            db.query(HousekeeperAssignment.housekeeper_id)
            .filter(and_(*assignment_filters))
            .distinct()
            .all()
        )
        assigned_ids = {row[0] for row in assigned_rows}

        not_scored_ids = assigned_ids - scored_ids
        for hk_id in not_scored_ids:
            hk = db.query(Housekeeper).filter(Housekeeper.id == hk_id).first()
            if hk is None:
                continue
            result.append(
                {
                    "id": hk.id,
                    "fullname": f"{hk.first_name} {hk.last_name}",
                    "photoUrl": hk.avatar_url,
                    "status": "not_scored",
                }
            )

        all_hk_ids = {
            row[0]
            for row in db.query(Housekeeper.id)
            .filter(Housekeeper.namespace_id == namespace_id)
            .all()
        }
        absent_ids = all_hk_ids - scored_ids - not_scored_ids
        for hk_id in absent_ids:
            hk = db.query(Housekeeper).filter(Housekeeper.id == hk_id).first()
            if hk is None:
                continue
            result.append(
                {
                    "id": hk.id,
                    "fullname": f"{hk.first_name} {hk.last_name}",
                    "photoUrl": hk.avatar_url,
                    "status": "absent",
                }
            )

    return result


def get_kpi_stars_dishes(
    db: Session,
    namespace_id: int,
    stat_date: str | None,
) -> dict[int, float | None]:
    date_from, date_to = resolve_date_range(stat_date, stat_date)

    rows = (
        db.query(DishesSurvey.dish_id, func.avg(DishesSurvey.Q))
        .filter(
            and_(
                DishesSurvey.namespace_id == namespace_id,
                DishesSurvey.created_at >= date_from,
                DishesSurvey.created_at <= date_to,
            )
        )
        .group_by(DishesSurvey.dish_id)
        .all()
    )

    return {dish_id: round(avg, 2) if avg is not None else None for dish_id, avg in rows}
