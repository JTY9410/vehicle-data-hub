from flask import current_app
from werkzeug.security import generate_password_hash

from apps.auth import is_banned_admin_password
from apps.extensions import db
from apps.models import User


def seed_admin_user(*, force_password: bool = False) -> User:
    """환경변수가 있을 때만 관리자를 만든다. force_password 시에만 해시 갱신.

    Vercel cold start마다 scrypt 재해시를 돌리면 요청이 수십 초로 늘어난다.
    """
    username = (current_app.config.get("ADMIN_USERNAME") or "").strip()
    password = current_app.config.get("ADMIN_PASSWORD") or ""
    if not username or not password:
        raise RuntimeError(
            "ADMIN_USERNAME과 ADMIN_PASSWORD가 없으면 시드하지 않습니다. /setup 을 사용하세요."
        )
    if is_banned_admin_password(password):
        raise RuntimeError("공유된 초안 비밀번호는 폐기되었습니다. 새 비밀번호를 설정하세요.")
    user = db.session.execute(
        db.select(User).filter_by(username=username)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            username=username,
            password_hash=generate_password_hash(password, method="scrypt"),
        )
        db.session.add(user)
        db.session.commit()
        return user
    if force_password:
        user.password_hash = generate_password_hash(password, method="scrypt")
        db.session.commit()
    return user
