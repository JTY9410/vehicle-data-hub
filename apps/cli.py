from flask import current_app
from werkzeug.security import generate_password_hash

from apps.extensions import db
from apps.models import User


def seed_admin_user(*, force_password: bool = False) -> User:
    """관리자 계정이 없을 때만 생성. force_password 시에만 해시 갱신.

    Vercel cold start마다 scrypt 재해시를 돌리면 요청이 수십 초로 늘어난다.
    """
    username = current_app.config["ADMIN_USERNAME"]
    password = current_app.config["ADMIN_PASSWORD"]
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
