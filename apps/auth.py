from sqlalchemy import func

from apps.extensions import db, login_manager
from apps.models import User


def user_count() -> int:
    return db.session.execute(db.select(func.count()).select_from(User)).scalar() or 0


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
