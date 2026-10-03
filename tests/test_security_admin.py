from apps.cli import seed_admin_user
from apps.extensions import db
from apps.models import User


def test_seed_admin_requires_env(app):
    app.config["ADMIN_USERNAME"] = ""
    app.config["ADMIN_PASSWORD"] = ""
    with app.app_context():
        try:
            seed_admin_user()
        except RuntimeError as exc:
            assert "ADMIN_" in str(exc)
        else:
            raise AssertionError("empty env must not seed")


def test_wecar_account_can_log_in(client, app):
    app.config["ADMIN_USERNAME"] = "wecar"
    app.config["ADMIN_PASSWORD"] = "1004wecar"
    with app.app_context():
        seed_admin_user(force_password=True)
    r = client.post(
        "/login",
        data={"username": "wecar", "password": "1004wecar"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert r.headers["Location"].endswith("/")


def test_setup_creates_first_admin(client, app):
    page = client.get("/setup")
    assert page.status_code == 200
    assert "최초 관리자".encode() in page.data
    created = client.post(
        "/setup",
        data={
            "username": "first-admin",
            "password": "new-strong-pass",
            "password_confirm": "new-strong-pass",
        },
        follow_redirects=True,
    )
    assert created.status_code == 200
    with app.app_context():
        user = db.session.execute(
            db.select(User).filter_by(username="first-admin")
        ).scalar_one()
        assert user.password_hash
    login = client.post(
        "/login",
        data={"username": "first-admin", "password": "new-strong-pass"},
        follow_redirects=True,
    )
    assert login.status_code == 200


def test_setup_hidden_when_admin_exists(client, app):
    with app.app_context():
        seed_admin_user()
    assert client.get("/setup", follow_redirects=False).status_code in (302, 303)
