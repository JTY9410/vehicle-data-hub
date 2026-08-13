import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "wecar")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1004wecar")
    MAX_CONTENT_LENGTH = 512 * 1024 * 1024
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    API_PER_PAGE_MAX = 100
