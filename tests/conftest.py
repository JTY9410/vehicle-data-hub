import pytest

from apps import create_app
from apps.extensions import db
import config as config_module

TEST_ADMIN_USERNAME = "testadmin"
TEST_ADMIN_PASSWORD = "test-admin-pass"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ADMIN_USERNAME", TEST_ADMIN_USERNAME)
    monkeypatch.setenv("ADMIN_PASSWORD", TEST_ADMIN_PASSWORD)
    # Config URI/ENGINE_OPTIONS are baked at import from .env — override before create_app.
    monkeypatch.setattr(config_module.Config, "SQLALCHEMY_DATABASE_URI", db_url)
    monkeypatch.setattr(config_module.Config, "SQLALCHEMY_ENGINE_OPTIONS", {}, raising=False)
    monkeypatch.setattr(config_module.Config, "ADMIN_USERNAME", TEST_ADMIN_USERNAME)
    monkeypatch.setattr(config_module.Config, "ADMIN_PASSWORD", TEST_ADMIN_PASSWORD)
    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_ENGINE_OPTIONS={},
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
