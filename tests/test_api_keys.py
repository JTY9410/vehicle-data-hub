from apps.extensions import db
from apps.models import User
from apps.services.api_keys import create_api_key, verify_api_key


def test_api_key_roundtrip(app):
    with app.app_context():
        from apps.services.api_keys import reveal_api_key

        row, raw = create_api_key("partner")
        assert row.key_prefix == raw[:8]
        assert verify_api_key(raw) is not None
        assert verify_api_key("bogus") is None
        assert reveal_api_key(row.id) == raw


def test_seed_admin(app):
    with app.app_context():
        from apps.cli import seed_admin_user

        seed_admin_user()
        u = db.session.execute(db.select(User).filter_by(username="wecar")).scalar_one()
        assert u.password_hash
