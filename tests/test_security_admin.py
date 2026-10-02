from pathlib import Path

from apps.auth import is_banned_admin_password
from apps.cli import seed_admin_user
from apps.extensions import db
from apps.models import User
from tests.conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME


ROOT = Path(__file__).resolve().parents[1]
SCAN_PATHS = (
    "config.py",
    "README.md",
    "agent.md",
    "pro.md",
    "AGENTS.md",
    ".env.example",
    "entrypoint.sh",
    "apps",
    "templates",
)


def test_config_has_no_default_admin_password():
    text = (ROOT / "config.py").read_text(encoding="utf-8")
    assert "1004wecar" not in text
    assert 'os.environ.get("ADMIN_PASSWORD", "")' in text
    assert is_banned_admin_password("1004wecar")


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


def test_seed_admin_rejects_draft_password(app):
    app.config["ADMIN_USERNAME"] = "admin"
    app.config["ADMIN_PASSWORD"] = "1004wecar"
    with app.app_context():
        try:
            seed_admin_user()
        except RuntimeError as exc:
            assert "초안" in str(exc) or "폐기" in str(exc)
        else:
            raise AssertionError("draft password must not seed")


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


def test_login_rejects_draft_password(client, app):
    with app.app_context():
        seed_admin_user()
    r = client.post(
        "/login",
        data={"username": TEST_ADMIN_USERNAME, "password": "1004wecar"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "초안".encode() in r.data or "폐기".encode() in r.data


def test_product_files_do_not_publish_draft_password():
    leaked = []
    for rel in SCAN_PATHS:
        path = ROOT / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if "1004wecar" in text:
                leaked.append(rel)
            continue
        for child in path.rglob("*"):
            if child.suffix not in {".py", ".md", ".html", ".sh", ".example", ".mdc"} and child.name != ".env.example":
                continue
            if "1004wecar" in child.read_text(encoding="utf-8"):
                leaked.append(str(child.relative_to(ROOT)))
    assert leaked == []
