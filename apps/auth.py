from apps.extensions import db, login_manager
from apps.models import User


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
