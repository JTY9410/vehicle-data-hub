"""Supabase/Postgres 비용 큰 쿼리 식별과 안전한 건수 추정."""

from __future__ import annotations

from sqlalchemy import Select, text

from apps.extensions import db

_COUNT_TABLES = frozenset(
    {
        "vehicles",
        "vehicle_maker",
        "vehicle_model",
        "vehicle_model_detail",
        "vehicle_grade",
        "vehicle_grade_detail",
        "import_jobs",
        "users",
        "api_keys",
    }
)


def estimate_row_count(table: str) -> int:
    """pg_class.reltuples 우선. 미분석(-1)이어도 COUNT(*) 풀스캔은 하지 않는다."""
    if table not in _COUNT_TABLES:
        raise ValueError(f"unsupported table: {table}")
    try:
        est = db.session.execute(
            text(
                """
                SELECT c.reltuples::bigint
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = :t
                  AND n.nspname = 'public'
                  AND c.relkind = 'r'
                """
            ),
            {"t": table},
        ).scalar()
        if est is not None:
            # -1 = never analyzed → 0으로 두고 목록 화면이 실제 행으로 보정
            return max(int(est), 0)
    except Exception:  # noqa: BLE001
        db.session.rollback()
    return int(
        db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
    )


def count_stmt_ids(stmt: Select, id_column) -> int:
    """서브쿼리에 전체 컬럼(특히 Text)·load_only 옵션을 넣지 않고 id만 센다."""
    inner = (
        stmt.order_by(None)
        .options(*())
        .with_only_columns(id_column, maintain_column_froms=True)
    )
    return int(
        db.session.execute(
            db.select(db.func.count()).select_from(inner.subquery())
        ).scalar_one()
        or 0
    )


def hot_queries(limit: int = 15) -> list[dict]:
    """pg_stat_statements 기준 총 실행시간 상위 쿼리. 확장 없으면 빈 목록."""
    try:
        rows = db.session.execute(
            text(
                """
                SELECT
                  round(total_exec_time::numeric, 1) AS total_ms,
                  round(mean_exec_time::numeric, 1) AS mean_ms,
                  calls,
                  round(
                    (100 * total_exec_time
                     / nullif(sum(total_exec_time) OVER (), 0))::numeric,
                    1
                  ) AS pct,
                  left(query, 240) AS query
                FROM pg_stat_statements
                WHERE query NOT ILIKE '%pg_stat_statements%'
                ORDER BY total_exec_time DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        ).mappings()
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        db.session.rollback()
        return []
