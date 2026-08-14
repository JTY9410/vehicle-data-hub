import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

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


def _prefer_supabase_pooler(url: str) -> str:
    """Direct db.*.supabase.co 는 IPv6-only인 경우가 많아 Vercel에서 실패 → pooler로 치환."""
    # postgresql+psycopg://user:pass@db.REF.supabase.co:5432/postgres?...
    marker = "@db."
    if ".supabase.co" not in url or marker not in url:
        # psycopg는 pgbouncer= 쿼리를 연결 옵션으로 해석해 실패함 → 제거
        return _strip_pgbouncer_query(url)
    try:
        pre, rest = url.split(marker, 1)
        host_and_more = rest  # REF.supabase.co:5432/postgres?...
        ref = host_and_more.split(".supabase.co", 1)[0]
        after = host_and_more.split(".supabase.co", 1)[1]  # :5432/postgres?...
        # user may be "postgres" — pooler wants postgres.REF
        scheme, creds = pre.split("://", 1)
        if ":" in creds:
            user, password = creds.split(":", 1)
        else:
            user, password = creds, ""
        if user == "postgres":
            user = f"postgres.{ref}"
        # Transaction pooler (serverless). prepared statements는 ENGINE_OPTIONS에서 비활성.
        path = after
        if path.startswith(":5432"):
            path = ":6543" + path[len(":5432") :]
        elif path.startswith("/"):
            path = ":6543" + path
        sep = "&" if "?" in path else "?"
        if "sslmode=" not in path:
            path = f"{path}{sep}sslmode=require"
        return _strip_pgbouncer_query(
            f"{scheme}://{user}:{password}@aws-0-ap-northeast-2.pooler.supabase.com{path}"
        )
    except Exception:  # noqa: BLE001
        return _strip_pgbouncer_query(url)


def _strip_pgbouncer_query(url: str) -> str:
    """psycopg3는 URL의 pgbouncer= 파라미터를 허용하지 않음."""
    if "pgbouncer=" not in url:
        return url
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "pgbouncer"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "wecar")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1004wecar")
    API_PER_PAGE_MAX = 100

    # CSRF / session (Vercel 서버리스에서 만료·Referer 누락 방지)
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_HEADERS = ["X-CSRFToken", "X-CSRF-Token"]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    _raw_db = os.environ.get("DATABASE_URL")
    if IS_VERCEL:
        uri = _normalize_database_url(
            _raw_db or "sqlite:////tmp/vehicle_hub.db"
        )
        uri = _prefer_supabase_pooler(uri)
        SQLALCHEMY_DATABASE_URI = uri
        SQLALCHEMY_ENGINE_OPTIONS = {
            "poolclass": NullPool,
            "connect_args": {
                "sslmode": "require",
                "prepare_threshold": None,
                "connect_timeout": 10,
            },
        }
        UPLOAD_FOLDER = Path("/tmp/vehicle_hub_uploads")
        MAX_CONTENT_LENGTH = 4 * 1024 * 1024
        # HTTPS 프록시(Vercel) 뒤에서 세션·CSRF가 깨지지 않도록
        SESSION_COOKIE_SECURE = True
        REMEMBER_COOKIE_SECURE = True
        SESSION_COOKIE_NAME = "vh_session"
        PREFERRED_URL_SCHEME = "https"
        WTF_CSRF_SSL_STRICT = False
    else:
        SQLALCHEMY_DATABASE_URI = _normalize_database_url(
            _raw_db or f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
        )
        UPLOAD_FOLDER = BASE_DIR / "uploads"
        MAX_CONTENT_LENGTH = 512 * 1024 * 1024
