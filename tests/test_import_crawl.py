from apps.extensions import db
from apps.models import Vehicle
from apps.services.crawl_client import iter_crawling_rows
from apps.services.import_crawl import import_from_crawl


def _item(**overrides):
    base = {
        "id": 10,
        "car_import_yn": "N",
        "site_type": "encar",
        "site_id": "s-10",
        "car_no": "12가3456",
        "car_year": "2020",
        "car_km": "10000",
        "car_price": "1500",
        "car_maker": "현대",
        "car_model": "쏘나타",
        "car_submodel": "DN8",
        "car_grade": "가솔린 2.0",
        "car_subgrade": "인스퍼레이션",
        "car_fuel": "가솔린",
        "car_mission": "오토",
        "car_color": "흰색",
        "car_location": "서울",
        "car_cc": "1999",
        "car_type": "세단",
        "car_seat": 5,
        "detail_info": '{"a":1}',
        "option_info": "opt",
        "unique_option_info": "uniq",
        "diag_info": "diag",
        "url_link": "https://example.com/10",
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_iter_crawling_rows_paginates_by_id_and_dedupes():
    calls = []

    def http_get(url, headers):
        calls.append(url)
        assert headers.get("x-api-key") == "k"
        if "offset=0" in url:
            return {
                "datas": [_item(id=1, site_id="a"), _item(id=2, site_id="b")],
                "total": 3,
                "limit": 2,
                "offset": 0,
            }
        if "offset=2" in url:
            return {
                "datas": [_item(id=2, site_id="b"), _item(id=3, site_id="c")],
                "total": 3,
                "limit": 2,
                "offset": 2,
            }
        return {"datas": [], "total": 3, "limit": 2, "offset": 99}

    rows = list(
        iter_crawling_rows(
            base_url="https://crawl.example.test",
            api_key="k",
            limit=2,
            http_get=http_get,
        )
    )
    assert [r["id"] for r in rows] == [1, 2, 3]
    assert any("offset=2" in u for u in calls)


def test_import_from_crawl_replaces_all_and_rejects_rental_and_9999(app):
    with app.app_context():
        db.session.add(
            Vehicle(site_type="encar", site_id="old-1", car_no="12가0001", car_price=100)
        )
        db.session.commit()

        items = [
            _item(id=1, site_id="keep", car_no="12가1111", car_price="1800"),
            _item(id=2, site_id="rent", car_no="12하1111", car_price="1800"),
            _item(id=3, site_id="bad", car_no="12가2222", car_price="9999"),
            _item(id=4, site_id="heo", car_no="88허1234", car_price="2000"),
            _item(id=5, site_id="ho", car_no="01호9998", car_price="2000"),
        ]
        job = import_from_crawl(
            source="cli",
            fetch_rows=lambda: items,
            replace=True,
        )
        assert job.status == "completed"
        assert job.saved_rows == 1
        assert job.rejected_rows == 4
        cars = db.session.execute(db.select(Vehicle)).scalars().all()
        assert len(cars) == 1
        kept = cars[0]
        assert kept.site_id == "keep"
        assert kept.source_id == "1"
        assert kept.car_price == 1800
        assert kept.option_info == "opt"
        assert kept.unique_option_info == "uniq"
        assert kept.car_seat == "5"


def test_upload_post_syncs_from_crawl(client, app, monkeypatch):
    from apps.cli import seed_admin_user

    items = [_item(id=7, site_id="web-1", car_no="12가7777", car_price="2100")]
    monkeypatch.setattr(
        "apps.services.import_crawl.iter_crawling_rows",
        lambda **_kwargs: items,
    )
    with app.app_context():
        seed_admin_user()
        app.config["CRAWL_API_KEY"] = "test-key"
        db.session.add(
            Vehicle(site_type="encar", site_id="stale", car_no="12가0000", car_price=50)
        )
        db.session.commit()

    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    r = client.post("/upload", follow_redirects=True)
    assert r.status_code == 200
    assert "저장".encode() in r.data or b"completed" in r.data or "작업".encode() in r.data

    with app.app_context():
        cars = db.session.execute(db.select(Vehicle)).scalars().all()
        assert len(cars) == 1
        assert cars[0].site_id == "web-1"
        assert cars[0].car_price == 2100
