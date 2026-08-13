from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from apps.extensions import db
from apps.models import Vehicle
from apps.services.api_keys import verify_api_key
from apps.services.import_csv import parse_date_bound

bp = Blueprint("api", __name__, url_prefix="/api/v1")

# CSV / API 필드 SSOT (업로드·응답 공통)
VEHICLE_FIELDS = (
    "id",
    "car_import_yn",
    "site_type",
    "site_id",
    "car_no",
    "car_year",
    "car_km",
    "car_price",
        "car_maker",
    "car_model",
    "car_submodel",
    "car_grade",
    "car_subgrade",
    "maker_no",
    "model_no",
    "mdetail_no",
    "grade_no",
    "gdetail_no",
    "car_fuel",
    "car_mission",
    "car_color",
    "car_location",
    "detail_info",
    "option_info",
    "diag_info",
    "url_link",
    "created_at",
    "car_cc",
    "car_type",
    "car_seat",
)


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        raw = request.headers.get("X-API-Key", "")
        key = verify_api_key(raw)
        if key is None:
            return jsonify(error="unauthorized"), 401
        return view(*args, **kwargs)

    return wrapped


def _vehicle_public(v: Vehicle) -> dict:
    """CSV 스키마와 동일한 키로 응답. id=원본 CSV id, created_at=CSV 저장일자(scraped_at)."""
    return {
        "id": v.source_id if v.source_id is not None else str(v.id),
        "db_id": v.id,
        "car_import_yn": v.car_import_yn,
        "site_type": v.site_type,
        "site_id": v.site_id,
        "car_no": v.car_no,
        "car_year": v.car_year,
        "car_km": v.car_km,
        "car_price": v.car_price,
        "car_maker": v.car_maker,
        "car_model": v.car_model,
        "car_submodel": v.car_submodel,
        "car_grade": v.car_grade,
        "car_subgrade": v.car_subgrade,
        "maker_no": v.maker_no,
        "model_no": v.model_no,
        "mdetail_no": v.mdetail_no,
        "grade_no": v.grade_no,
        "gdetail_no": v.gdetail_no,
        "car_fuel": v.car_fuel,
        "car_mission": v.car_mission,
        "car_color": v.car_color,
        "car_location": v.car_location,
        "detail_info": v.detail_info,
        "option_info": v.option_info,
        "diag_info": v.diag_info,
        "url_link": v.url_link,
        "created_at": v.scraped_at.isoformat() if v.scraped_at else None,
        "car_cc": v.car_cc,
        "car_type": v.car_type,
        "car_seat": v.car_seat,
        "price_unit": "만원",
    }


@bp.get("/vehicles")
@require_api_key
def list_vehicles():
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(
        max(int(request.args.get("per_page", 20)), 1),
        current_app.config["API_PER_PAGE_MAX"],
    )
    stmt = db.select(Vehicle)
    maker = request.args.get("maker")
    model = request.args.get("model")
    maker_no = (request.args.get("maker_no") or "").strip()
    model_no = (request.args.get("model_no") or "").strip()
    mdetail_no = (request.args.get("mdetail_no") or "").strip()
    grade_no = (request.args.get("grade_no") or "").strip()
    gdetail_no = (request.args.get("gdetail_no") or "").strip()
    site_type = request.args.get("site_type")
    year = request.args.get("year")
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    created_at_from = (request.args.get("created_at_from") or "").strip()
    created_at_to = (request.args.get("created_at_to") or "").strip()

    if maker_no:
        stmt = stmt.filter(Vehicle.maker_no == maker_no)
    if model_no:
        stmt = stmt.filter(Vehicle.model_no == model_no)
    if mdetail_no:
        stmt = stmt.filter(Vehicle.mdetail_no == mdetail_no)
    if grade_no:
        stmt = stmt.filter(Vehicle.grade_no == grade_no)
    if gdetail_no:
        stmt = stmt.filter(Vehicle.gdetail_no == gdetail_no)
    if maker:
        stmt = stmt.filter(Vehicle.car_maker == maker)
    if model:
        stmt = stmt.filter(Vehicle.car_model == model)
    if site_type:
        stmt = stmt.filter(Vehicle.site_type == site_type)
    if year:
        stmt = stmt.filter(Vehicle.car_year.contains(year))
    if price_min is not None:
        stmt = stmt.filter(Vehicle.car_price >= price_min)
    if price_max is not None:
        stmt = stmt.filter(Vehicle.car_price <= price_max)
    from_dt = parse_date_bound(created_at_from, end_of_day=False)
    to_dt = parse_date_bound(created_at_to, end_of_day=True)
    if from_dt is not None:
        stmt = stmt.filter(Vehicle.scraped_at >= from_dt)
    if to_dt is not None:
        stmt = stmt.filter(Vehicle.scraped_at <= to_dt)

    total = db.session.execute(
        db.select(db.func.count()).select_from(stmt.subquery())
    ).scalar_one()
    rows = db.session.execute(
        stmt.order_by(Vehicle.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()
    return jsonify(
        price_unit="만원",
        page=page,
        per_page=per_page,
        total=total,
        fields=list(VEHICLE_FIELDS),
        items=[_vehicle_public(v) for v in rows],
    )


@bp.get("/vehicles/search")
@require_api_key
def search_vehicles():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify(price_unit="만원", fields=list(VEHICLE_FIELDS), items=[])
    stmt = (
        db.select(Vehicle)
        .filter(
            db.or_(
                Vehicle.car_no.contains(q),
                Vehicle.car_model.contains(q),
                Vehicle.car_maker.contains(q),
            )
        )
        .order_by(Vehicle.id.desc())
        .limit(50)
    )
    rows = db.session.execute(stmt).scalars().all()
    return jsonify(
        price_unit="만원",
        fields=list(VEHICLE_FIELDS),
        items=[_vehicle_public(v) for v in rows],
    )


@bp.get("/vehicles/<int:vehicle_id>")
@require_api_key
def vehicle_detail(vehicle_id: int):
    v = db.session.get(Vehicle, vehicle_id)
    if v is None:
        return jsonify(error="not_found"), 404
    return jsonify(_vehicle_public(v))
