from flask import current_app
from werkzeug.security import generate_password_hash

from apps.extensions import db
from apps.models import User


def seed_admin_user() -> User:
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
    else:
        user.password_hash = generate_password_hash(password, method="scrypt")
    db.session.commit()
    return user
