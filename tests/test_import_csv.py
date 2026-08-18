from pathlib import Path

from apps.extensions import db
from apps.models import Vehicle
from apps.routes.api import VEHICLE_FIELDS, _vehicle_public
from apps.services.api_keys import create_api_key
from apps.services.import_csv import import_csv_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


def test_import_filters_and_upsert(app):
    with app.app_context():
        job = import_csv_file(FIXTURE, source="cli")
        assert job.status == "completed"
        assert job.saved_rows >= 1
        assert job.rejected_rows >= 2
        cars = db.session.execute(db.select(Vehicle)).scalars().all()
        assert all("하" not in (c.car_no or "") for c in cars)
        assert all(c.car_price is not None and 0 < c.car_price < 9999 for c in cars)
        upserted = db.session.execute(
            db.select(Vehicle).filter_by(site_type="encar", site_id="site-upsert")
        ).scalar_one()
        assert upserted.car_price == 2200
        assert upserted.car_color == "검정색"
        kept = db.session.execute(
            db.select(Vehicle).filter_by(site_type="encar", site_id="site-keep")
        ).scalar_one()
        assert kept.source_id == "1"


def test_import_stores_all_csv_fields_and_api_shape(app, client):
    with app.app_context():
        import_csv_file(FIXTURE, source="cli")
        kept = db.session.execute(
            db.select(Vehicle).filter_by(site_type="encar", site_id="site-keep")
        ).scalar_one()
        assert kept.source_id == "1"
        assert kept.car_import_yn == "N"
        assert kept.car_no == "12가3456"
        assert kept.car_year == "2020"
        assert kept.car_km == 10000
        assert kept.car_price == 1500
        assert kept.car_maker == "현대"
        assert kept.car_model == "쏘나타"
        assert kept.car_submodel == "DN8"
        assert kept.car_grade == "가솔린 2.0"
        assert kept.car_subgrade == "인스퍼레이션"
        assert kept.car_fuel == "가솔린"
        assert kept.car_mission == "오토"
        assert kept.car_color == "흰색"
        assert kept.car_location == "서울"
        assert kept.detail_info == '{"a":1}'
        assert kept.option_info == "opt"
        assert kept.diag_info == "diag"
        assert kept.url_link == "https://example.com/1"
        assert kept.scraped_at is not None
        assert kept.car_cc == "1999"
        assert kept.car_type == "세단"
        assert kept.car_seat == "5"

        payload = _vehicle_public(kept)
        for field in VEHICLE_FIELDS:
            assert field in payload, field
        assert payload["id"] == "1"
        assert payload["created_at"] is not None
        assert payload["price_unit"] == "만원"
        assert "db_id" in payload

        _, raw = create_api_key("fields")
        vid = kept.id

    r = client.get(f"/api/v1/vehicles/{vid}", headers={"X-API-Key": raw})
    assert r.status_code == 200
    body = r.get_json()
    for field in VEHICLE_FIELDS:
        assert field in body
    assert body["id"] == "1"
    assert body["car_seat"] == "5"
    assert body["detail_info"] == '{"a":1}'
    assert body["price_unit"] == "만원"
