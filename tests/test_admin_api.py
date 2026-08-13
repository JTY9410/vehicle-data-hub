from pathlib import Path

from apps.cli import seed_admin_user
from apps.extensions import db
from apps.models import Vehicle, VehicleMaker, VehicleModel
from apps.services.api_keys import create_api_key

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


def test_dashboard_requires_login(client):
    assert client.get("/").status_code in (302, 401)


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
    body = r.get_json()
    assert body.get("price_unit") == "만원"
    assert "items" in body
    r = client.get(f"/api/v1/vehicles/{vid}", headers={"X-API-Key": raw})
    assert r.status_code == 200
    body = r.get_json()
    assert body["car_price"] == 2000
    assert "detail_info" in body
    assert "created_at" in body
    assert "car_seat" in body
