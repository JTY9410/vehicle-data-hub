import hashlib
import secrets

from apps.extensions import db
from apps.models import ApiKey, utcnow


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_api_key(name: str) -> tuple[ApiKey, str]:
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    row = ApiKey(name=name, key_prefix=prefix, key_hash=_hash_key(raw), is_active=True)
    db.session.add(row)
    db.session.commit()
    return row, raw


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
    db.session.commit()
    return True
