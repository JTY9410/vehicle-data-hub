from pathlib import Path

from apps.cli import seed_admin_user
from apps.extensions import db
from apps.models import Vehicle, VehicleMaker, VehicleModel
from apps.services.api_keys import create_api_key

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


def test_dashboard_requires_login(client):
    assert client.get("/").status_code in (302, 401)


def test_db_stats_requires_login(client):
    assert client.get("/db-stats").status_code in (302, 401)


def test_api_key_title_reveal_and_copy_payload(client, app):
    with app.app_context():
        seed_admin_user()
        row, raw = create_api_key("popup-key")
        kid = row.id
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    page = client.get("/api-keys")
    assert page.status_code == 200
    assert b"key-title" in page.data
    rev = client.get(f"/api-keys/{kid}/reveal")
    assert rev.status_code == 200
    body = rev.get_json()
    assert body["ok"] is True
    assert body["key"] == raw


def test_login_and_upload(client, app):
    with app.app_context():
        seed_admin_user()
    r = client.post(
        "/login",
        data={"username": "wecar", "password": "1004wecar"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with FIXTURE.open("rb") as fh:
        r = client.post(
            "/upload",
            data={"file": (fh, "sample.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    assert r.status_code == 200
    assert b"saved" in r.data.lower() or "저장".encode() in r.data or b"completed" in r.data or "작업".encode() in r.data


def test_vehicles_search_by_maker_model_subgrade(client, app):
    with app.app_context():
        seed_admin_user()
        db.session.add(VehicleMaker(maker_no="10055", maker_name="현대"))
        db.session.add(
            VehicleModel(model_no="2001", maker_no="10055", model_name="쏘나타")
        )
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="v-1",
                car_no="12가1000",
                car_price=2000,
                car_maker="현대",
                car_model="쏘나타",
                car_grade="가솔린 2.0",
                car_subgrade="인스퍼레이션",
                maker_no="10055",
                model_no="2001",
            )
        )
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="v-2",
                car_no="12가2000",
                car_price=3000,
                car_maker="기아",
                car_model="K5",
                car_grade="가솔린 1.6",
                car_subgrade="시그니처",
                maker_no="10001",
                model_no="2002",
            )
        )
        db.session.commit()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    r = client.get("/vehicles?maker_no=10055&model_no=2001")
    assert r.status_code == 200
    assert "인스퍼레이션".encode() in r.data
    assert "시그니처".encode() not in r.data


def test_vehicles_shows_fuel_and_filters_by_fuel(client, app):
    with app.app_context():
        seed_admin_user()
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="fuel-g",
                car_no="12가1111",
                car_price=2000,
                car_maker="현대",
                car_model="쏘나타",
                car_fuel="가솔린",
            )
        )
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="fuel-d",
                car_no="12가2222",
                car_price=1800,
                car_maker="현대",
                car_model="싼타페",
                car_fuel="디젤",
            )
        )
        db.session.commit()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    page = client.get("/vehicles")
    assert page.status_code == 200
    assert ">연료<".encode() in page.data
    assert "가솔린".encode() in page.data
    assert "디젤".encode() in page.data
    filtered = client.get("/vehicles?fuel=디젤")
    assert filtered.status_code == 200
    assert "싼타페".encode() in filtered.data
    assert "쏘나타".encode() not in filtered.data


def test_api_search_and_list_by_fuel(client, app):
    with app.app_context():
        seed_admin_user()
        _, raw = create_api_key("fuel")
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="api-fuel-1",
                car_no="12가3333",
                car_price=2100,
                car_maker="기아",
                car_model="K5",
                car_fuel="하이브리드",
            )
        )
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="api-fuel-2",
                car_no="12가4444",
                car_price=1900,
                car_maker="기아",
                car_model="스포티지",
                car_fuel="가솔린",
            )
        )
        db.session.commit()
    headers = {"X-API-Key": raw}
    listed = client.get("/api/v1/vehicles?fuel=하이브리드", headers=headers)
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert len(items) == 1
    assert items[0]["car_fuel"] == "하이브리드"
    assert items[0]["car_model"] == "K5"
    searched = client.get("/api/v1/vehicles/search?q=하이브리드", headers=headers)
    assert searched.status_code == 200
    models = {row["car_model"] for row in searched.get_json()["items"]}
    assert "K5" in models
    assert "스포티지" not in models


def test_api_docs_page(client, app):
    with app.app_context():
        seed_admin_user()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    r = client.get("/api-keys/docs")
    assert r.status_code == 200
    assert "API 명세서".encode() in r.data
    assert b"X-API-Key" in r.data
    assert b"car_seat" in r.data


def test_reset_dialog_markup(client, app):
    with app.app_context():
        from apps.cli import seed_admin_user

        seed_admin_user()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    r = client.get("/")
    assert r.status_code == 200
    assert b'id="resetDataDialog"' in r.data
    assert b"showModal" in r.data
    assert b"openResetDialog" in r.data
    with app.app_context():
        seed_admin_user()
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="r-1",
                car_no="12가3000",
                car_price=1500,
                car_maker="현대",
                car_model="아반떼",
            )
        )
        db.session.commit()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    r = client.post("/reset-data", data={"confirm": "NO"}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert db.session.execute(db.select(db.func.count()).select_from(Vehicle)).scalar_one() == 1
    r = client.post("/reset-data", data={"confirm": "DELETE"}, follow_redirects=True)
    assert r.status_code == 200
    assert "초기화".encode() in r.data
    with app.app_context():
        assert db.session.execute(db.select(db.func.count()).select_from(Vehicle)).scalar_one() == 0


def test_api_unauthorized(client):
    assert client.get("/api/v1/vehicles").status_code == 401


def test_api_list_and_detail(client, app):
    with app.app_context():
        seed_admin_user()
        _, raw = create_api_key("t")
        v = Vehicle(
            site_type="encar",
            site_id="api-1",
            car_no="12가9999",
            car_price=2000,
            car_maker="현대",
            car_model="아반떼",
        )
        db.session.add(v)
        db.session.commit()
        vid = v.id
    r = client.get("/api/v1/vehicles", headers={"X-API-Key": raw})
    assert r.status_code == 200
    assert r.headers.get("Access-Control-Allow-Origin") == "*"
    r = client.get("/api/v1/vehicles", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("price_unit") == "만원"
    assert "items" in body
    assert body["items"]
    assert "detail_info" not in body["items"][0]
    assert "url_link" in body["items"][0]
    r = client.get(f"/api/v1/vehicles/{vid}", headers={"X-API-Key": raw})
    assert r.status_code == 200
    body = r.get_json()
    assert body["car_price"] == 2000
    assert "detail_info" in body
    assert "created_at" in body
    assert "car_seat" in body
