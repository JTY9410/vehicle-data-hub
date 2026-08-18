from apps.extensions import db
from apps.models import Vehicle
from apps.services.encar_attrs import (
    normalize_color,
    normalize_mission,
    normalize_type,
    remap_vehicle_attrs,
)
from apps.services.import_csv import import_csv_file
from apps.cli import seed_admin_user


def test_normalize_mission_color_type_encar():
    assert normalize_mission("자동") == "오토"
    assert normalize_mission("A/T") == "오토"
    assert normalize_mission("MT") == "수동"
    assert normalize_mission("무단변속기") == "CVT"
    assert normalize_mission("DCT") == "오토"
    assert normalize_color("파란색") == "청색"
    assert normalize_color("검정") == "검정색"
    assert normalize_color("미선택") is None
    assert normalize_type("화물차") == "화물"
    assert normalize_type("승합차") == "승합"
    assert normalize_type("RV/SUV") == "SUV"
    assert normalize_type("경승합차") == "승합"


def test_import_normalizes_encar_attrs(app, tmp_path):
    csv_path = tmp_path / "attrs.csv"
    csv_path.write_text(
        "id,car_import_yn,site_type,site_id,car_no,car_year,car_km,car_price,"
        "car_maker,car_model,car_submodel,car_grade,car_subgrade,car_fuel,"
        "car_mission,car_color,car_location,detail_info,option_info,diag_info,"
        "url_link,created_at,car_cc,car_type,car_seat\n"
        "1,N,encar,attr-1,12가9990,2020,10000,1500,현대,쏘나타,,,,가솔린,"
        "무단변속기,파란색,서울,,,,,2024-01-01T00:00:00+00:00,,화물차,\n",
        encoding="utf-8",
    )
    with app.app_context():
        job = import_csv_file(csv_path, source="cli")
        assert job.status == "completed"
        row = db.session.execute(
            db.select(Vehicle).filter_by(site_id="attr-1")
        ).scalar_one()
        assert row.car_mission == "CVT"
        assert row.car_color == "청색"
        assert row.car_type == "화물"


def test_remap_vehicle_attrs(app):
    with app.app_context():
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="attr-old",
                car_no="12가9991",
                car_price=1100,
                car_mission="무단변속기",
                car_color="파란색",
                car_type="화물차",
            )
        )
        db.session.commit()
        result = remap_vehicle_attrs()
        assert result["updated"] >= 1
        row = db.session.execute(
            db.select(Vehicle).filter_by(site_id="attr-old")
        ).scalar_one()
        assert row.car_mission == "CVT"
        assert row.car_color == "청색"
        assert row.car_type == "화물"


def test_upload_page_can_reset_imported_data(client, app):
    with app.app_context():
        seed_admin_user()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    page = client.get("/upload")
    assert page.status_code == 200
    assert b'id="resetDataDialog"' in page.data
    assert "데이터 초기화".encode() in page.data
