from flask import Blueprint, jsonify

from apps.extensions import db

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz():
    db_ok = False
    db_error = None
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        db_error = str(exc)[:300]
    payload = {"status": "ok" if db_ok else "degraded", "db": db_ok}
    if db_error:
        payload["db_error"] = db_error
    return jsonify(payload), (200 if db_ok else 503)
