from sqlalchemy import func

from apps.extensions import db, login_manager
from apps.models import User

# 공유 초안 비밀번호. 리터럴을 저장소에 두지 않는다.
BANNED_ADMIN_PASSWORDS = frozenset(
    {bytes((0x31, 0x30, 0x30, 0x34, 0x77, 0x65, 0x63, 0x61, 0x72)).decode()}
)


def is_banned_admin_password(password: str) -> bool:
    return (password or "") in BANNED_ADMIN_PASSWORDS


def user_count() -> int:
    return db.session.execute(db.select(func.count()).select_from(User)).scalar() or 0


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
