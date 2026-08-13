from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from apps.extensions import db
from apps.models import Vehicle
from apps.services.api_keys import verify_api_key

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        raw = request.headers.get("X-API-Key", "")
        key = verify_api_key(raw)
        if key is None:
            return jsonify(error="unauthorized"), 401
        return view(*args, **kwargs)

    return wrapped


def _vehicle_public(v: Vehicle, include_detail: bool = False) -> dict:
    data = {
        "id": v.id,
        "site_type": v.site_type,
        "site_id": v.site_id,
        "car_no": v.car_no,
        "car_year": v.car_year,
        "car_km": v.car_km,
        "car_price": v.car_price,
        "price_unit": "만원",
        "car_maker": v.car_maker,
        "car_model": v.car_model,
        "car_submodel": v.car_submodel,
        "car_grade": v.car_grade,
        "car_subgrade": v.car_subgrade,
        "car_fuel": v.car_fuel,
        "car_mission": v.car_mission,
        "car_color": v.car_color,
        "car_location": v.car_location,
        "car_import_yn": v.car_import_yn,
        "car_cc": v.car_cc,
        "car_type": v.car_type,
        "car_seat": v.car_seat,
        "url_link": v.url_link,
        "scraped_at": v.scraped_at.isoformat() if v.scraped_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }
    if include_detail:
        data["detail_info"] = v.detail_info
        data["option_info"] = v.option_info
        data["diag_info"] = v.diag_info
    return data


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
    site_type = request.args.get("site_type")
    year = request.args.get("year")
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
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
        items=[_vehicle_public(v) for v in rows],
    )


@bp.get("/vehicles/search")
@require_api_key
def search_vehicles():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify(price_unit="만원", items=[])
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
    return jsonify(price_unit="만원", items=[_vehicle_public(v) for v in rows])


@bp.get("/vehicles/<int:vehicle_id>")
@require_api_key
def vehicle_detail(vehicle_id: int):
    v = db.session.get(Vehicle, vehicle_id)
    if v is None:
        return jsonify(error="not_found"), 404
    return jsonify(_vehicle_public(v, include_detail=True))
