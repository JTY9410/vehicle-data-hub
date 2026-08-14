from config import (
    _normalize_database_url,
    _prefer_supabase_pooler,
    _strip_pgbouncer_query,
)


def test_normalize_database_url_supabase_style():
    assert _normalize_database_url(
        "postgresql://user:pass@db.example.supabase.co:5432/postgres"
    ).startswith("postgresql+psycopg://")
    assert _normalize_database_url(
        "postgres://user:pass@host:5432/db"
    ).startswith("postgresql+psycopg://")
    assert (
        _normalize_database_url("postgresql+psycopg://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )


def test_prefer_supabase_pooler_rewrites_direct_host():
    raw = (
        "postgresql+psycopg://postgres:%23secret"
        "@db.rastroihbytrjagdhzrn.supabase.co:5432/postgres"
    )
    out = _prefer_supabase_pooler(raw)
    assert "aws-0-ap-northeast-2.pooler.supabase.com" in out
    assert "postgres.rastroihbytrjagdhzrn" in out
    assert ":6543/" in out or ":6543?" in out or out.endswith(":6543/postgres") or ":6543/postgres" in out
    assert "sslmode=require" in out
    assert "pgbouncer=" not in out
    assert "@db." not in out


def test_prefer_supabase_pooler_leaves_pooler_unchanged():
    raw = (
        "postgresql+psycopg://postgres.ref:pass"
        "@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    assert _prefer_supabase_pooler(raw) == raw


def test_strip_pgbouncer_query_param():
    raw = (
        "postgresql+psycopg://postgres.ref:pass"
        "@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres?sslmode=require&pgbouncer=true"
    )
    out = _prefer_supabase_pooler(raw)
    assert "pgbouncer=" not in out
    assert "sslmode=require" in out
