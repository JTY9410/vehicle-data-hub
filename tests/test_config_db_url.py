from config import _normalize_database_url


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
