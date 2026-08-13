import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
IS_VERCEL = bool(os.environ.get("VERCEL"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "wecar")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1004wecar")
    API_PER_PAGE_MAX = 100

    if IS_VERCEL:
        # Ephemeral unless DATABASE_URL points to hosted Postgres
        SQLALCHEMY_DATABASE_URI = os.environ.get(
            "DATABASE_URL", "sqlite:////tmp/vehicle_hub.db"
        )
        UPLOAD_FOLDER = Path("/tmp/vehicle_hub_uploads")
        MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    else:
        SQLALCHEMY_DATABASE_URI = os.environ.get(
            "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
        )
        UPLOAD_FOLDER = BASE_DIR / "uploads"
        MAX_CONTENT_LENGTH = 512 * 1024 * 1024
