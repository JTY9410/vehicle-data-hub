import base64
import hashlib
import secrets

from flask import current_app

from apps.extensions import db
from apps.models import ApiKey, utcnow


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _seal(raw: str) -> str:
    key = hashlib.sha256(str(current_app.config["SECRET_KEY"]).encode()).digest()
    data = raw.encode("utf-8")
    mixed = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.urlsafe_b64encode(mixed).decode("ascii")


def _unseal(blob: str | None) -> str | None:
    if not blob:
        return None
    try:
        key = hashlib.sha256(str(current_app.config["SECRET_KEY"]).encode()).digest()
        data = base64.urlsafe_b64decode(blob.encode("ascii"))
        raw = bytes(b ^ key[i % len(key)] for i, b in enumerate(data)).decode("utf-8")
    except Exception:  # noqa: BLE001
        return None
    return raw or None


def create_api_key(name: str) -> tuple[ApiKey, str]:
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    row = ApiKey(
        name=name,
        key_prefix=prefix,
        key_hash=_hash_key(raw),
        key_secret=_seal(raw),
        is_active=True,
    )
    db.session.add(row)
    db.session.commit()
    return row, raw


def reveal_api_key(key_id: int) -> str | None:
    row = db.session.get(ApiKey, key_id)
    if row is None or not row.is_active:
        return None
    return _unseal(row.key_secret)


def request_header_api_key() -> str:
    from flask import request

    raw = (request.headers.get("X-API-Key") or "").strip()
    if raw:
        return raw
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def verify_api_key(raw: str) -> ApiKey | None:
    if not raw:
        return None
    digest = _hash_key(raw)
    row = db.session.execute(
        db.select(ApiKey).filter_by(key_hash=digest, is_active=True)
    ).scalar_one_or_none()
    if row is None:
        return None
    row.last_used_at = utcnow()
    db.session.commit()
    return row


def revoke_api_key(key_id: int) -> bool:
    row = db.session.get(ApiKey, key_id)
    if row is None:
        return False
    row.is_active = False
    row.key_secret = None
    db.session.commit()
    return True
