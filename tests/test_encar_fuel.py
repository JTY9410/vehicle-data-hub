from apps.extensions import db
from apps.models import Vehicle
from apps.services.api_keys import create_api_key
from apps.services.encar_fuel import ENCAR_FUELS, normalize_fuel
from apps.services.import_csv import import_csv_file
from apps.cli import seed_admin_user


def test_normalize_fuel_encar_aliases():
    assert normalize_fuel("가솔린") == "가솔린"
    assert normalize_fuel("휘발유") == "가솔린"
    assert normalize_fuel("Gasoline") == "가솔린"
    assert normalize_fuel("경유") == "디젤"
    assert normalize_fuel("LPi") == "LPG"
    assert normalize_fuel("가솔린 하이브리드") == "하이브리드"
    assert normalize_fuel("가솔린+전기") == "하이브리드"
    assert normalize_fuel("PHEV") == "하이브리드"
    assert normalize_fuel("전기차") == "전기"
    assert normalize_fuel("수소전기") == "수소"
    assert normalize_fuel("NULL") is None
    assert "가솔린" in ENCAR_FUELS
    assert "수소" in ENCAR_FUELS


def test_import_maps_csv_fuel_to_encar_name(app, tmp_path):
    csv_path = tmp_path / "fuel.csv"
    csv_path.write_text(
        "id,car_import_yn,site_type,site_id,car_no,car_year,car_km,car_price,"
        "car_maker,car_model,car_submodel,car_grade,car_subgrade,car_fuel,"
        "car_mission,car_color,car_location,detail_info,option_info,diag_info,"
        "url_link,created_at,car_cc,car_type,car_seat\n"
        "1,N,encar,fuel-alias,12가5555,2020,10000,1500,현대,쏘나타,,,,휘발유,"
        "오토,흰색,서울,,,,,2024-01-01T00:00:00+00:00,,,\n",
        encoding="utf-8",
    )
    with app.app_context():
        job = import_csv_file(csv_path, source="cli")
        assert job.status == "completed"
        row = db.session.execute(
            db.select(Vehicle).filter_by(site_type="encar", site_id="fuel-alias")
        ).scalar_one()
        assert row.car_fuel == "가솔린"


def test_admin_fuel_dropdown_and_api_alias_filter(client, app):
    with app.app_context():
        seed_admin_user()
        _, raw = create_api_key("fuel-alias")
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="fuel-canon",
                car_no="12가6666",
                car_price=2000,
                car_maker="현대",
                car_model="아반떼",
                car_fuel="가솔린",
            )
        )
        db.session.commit()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    page = client.get("/vehicles")
    assert page.status_code == 200
    assert b'id="fuel"' in page.data
    assert b"<select" in page.data
    assert "가솔린".encode() in page.data
    headers = {"X-API-Key": raw}
    listed = client.get("/api/v1/vehicles?fuel=휘발유", headers=headers)
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert len(items) == 1
    assert items[0]["car_fuel"] == "가솔린"


def test_remap_vehicle_fuels(app):
    from apps.services.encar_fuel import remap_vehicle_fuels

    with app.app_context():
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="fuel-old",
                car_no="12가7777",
                car_price=1200,
                car_fuel="휘발유",
            )
        )
        db.session.commit()
        result = remap_vehicle_fuels()
        assert result["updated"] >= 1
        row = db.session.execute(
            db.select(Vehicle).filter_by(site_id="fuel-old")
        ).scalar_one()
        assert row.car_fuel == "가솔린"
