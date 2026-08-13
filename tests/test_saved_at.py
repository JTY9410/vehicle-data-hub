from datetime import datetime, timezone

from apps.services.import_csv import csv_row_saved_at, parse_csv_saved_at, parse_date_bound


def test_parse_csv_saved_at_formats():
    assert parse_csv_saved_at("2026-08-06 00:00:24") == datetime(
        2026, 8, 6, 0, 0, 24, tzinfo=timezone.utc
    )
    assert parse_csv_saved_at("2026-03-05 10:15:59") == datetime(
        2026, 3, 5, 10, 15, 59, tzinfo=timezone.utc
    )
    assert parse_csv_saved_at("2024-01-01T00:00:00+00:00") == datetime(
        2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc
    )
    assert parse_csv_saved_at("2026/08/06") == datetime(
        2026, 8, 6, 0, 0, 0, tzinfo=timezone.utc
    )
    assert parse_csv_saved_at("") is None
    assert parse_csv_saved_at("NULL") is None


def test_csv_row_saved_at_prefers_created_at():
    assert csv_row_saved_at({"created_at": "2026-08-06 00:00:24"}).year == 2026
    assert csv_row_saved_at({"저장일자": "2026-08-01"}).day == 1


def test_parse_date_bound_end_of_day():
    start = parse_date_bound("2026-08-01", end_of_day=False)
    end = parse_date_bound("2026-08-01", end_of_day=True)
    assert start == datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 1, 23, 59, 59, tzinfo=timezone.utc)
