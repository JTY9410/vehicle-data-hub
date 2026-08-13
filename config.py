import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
IS_VERCEL = bool(os.environ.get("VERCEL"))


def _normalize_database_url(url: str) -> str:
    """Supabase/Heroku 등 postgres:// → SQLAlchemy psycopg 드라이버 URL."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "wecar")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1004wecar")
    API_PER_PAGE_MAX = 100

    if IS_VERCEL:
        # Ephemeral unless DATABASE_URL points to hosted Postgres (e.g. Supabase)
        SQLALCHEMY_DATABASE_URI = _normalize_database_url(
            os.environ.get("DATABASE_URL", "sqlite:////tmp/vehicle_hub.db")
        )
        UPLOAD_FOLDER = Path("/tmp/vehicle_hub_uploads")
        MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    else:
        SQLALCHEMY_DATABASE_URI = _normalize_database_url(
            os.environ.get(
                "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
            )
        )
        UPLOAD_FOLDER = BASE_DIR / "uploads"
        MAX_CONTENT_LENGTH = 512 * 1024 * 1024
