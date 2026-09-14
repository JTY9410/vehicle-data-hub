from datetime import datetime
from zoneinfo import ZoneInfo

from apps.cli import seed_admin_user
from apps.extensions import db
from apps.models import Vehicle
from apps.services.import_crawl import consume_queued_collect, import_from_crawl, item_to_row
from apps.services.scheduler import next_sunday_midnight_kst
from apps.services.settings import crawl_credentials, crawl_key_configured, set_setting


def test_item_to_row_keeps_unique_option_and_inspected_at_columns():
    row = item_to_row(
        {
            "id": 9,
            "site_type": "encar",
            "site_id": "x",
            "option_info": "opt",
            "unique_option_info": "sunroof",
            "inspected_at": "2024-05-01",
            "car_seat": 5,
        }
    )
    assert row["option_info"] == "opt"
    assert row["unique_option_info"] == "sunroof"
    assert row["inspected_at"] == "2024-05-01"
    assert row["id"] == "9"
    assert row["car_seat"] == "5"


def test_import_stores_crawl_fields_in_own_columns(app):
    with app.app_context():
        job = import_from_crawl(
            source="cli",
            fetch_rows=lambda: [
                {
                    "id": 1,
                    "car_import_yn": "N",
                    "site_type": "encar",
                    "site_id": "col-1",
                    "car_no": "12가1111",
                    "car_year": "2020",
                    "car_km": "10000",
                    "car_price": "1800",
                    "car_maker": "현대",
                    "car_model": "쏘나타",
                    "car_fuel": "가솔린",
                    "car_mission": "오토",
                    "car_color": "흰색",
                    "car_type": "세단",
                    "car_seat": 5,
                    "option_info": "opt",
                    "unique_option_info": "sunroof",
                    "inspected_at": "2024-05-01",
                    "diag_info": "diag",
                    "url_link": "https://example.com/1",
                    "created_at": "2024-01-01T00:00:00+00:00",
                }
            ],
            replace=True,
        )
        assert job.status == "completed"
        kept = db.session.execute(
            db.select(Vehicle).filter_by(site_id="col-1")
        ).scalar_one()
        assert kept.option_info == "opt"
        assert kept.unique_option_info == "sunroof"
        assert kept.inspected_at is not None
        assert kept.inspected_at.date().isoformat() == "2024-05-01"
        assert kept.색상 == kept.car_color
        assert kept.미션 == kept.car_mission
        assert kept.차종 == kept.car_type
        assert kept.인승 == kept.car_seat
        assert kept.성능점검일 == kept.inspected_at
        assert kept.옵션정보 == "opt"
        assert kept.유용옵션 == "sunroof"
        assert kept.진단정보 == kept.diag_info


def test_item_to_row_copies_korean_api_keys():
    row = item_to_row(
        {
            "id": 2,
            "site_type": "encar",
            "site_id": "ko-1",
            "색상": "흰색",
            "미션": "오토",
            "차종": "세단",
            "인승": 5,
            "성능점검일": "2024-05-01",
            "옵션정보": "opt",
            "유용옵션": "sunroof",
            "진단정보": "diag",
        }
    )
    assert row["car_color"] == "흰색"
    assert row["car_mission"] == "오토"
    assert row["car_type"] == "세단"
    assert row["car_seat"] == "5"
    assert row["inspected_at"] == "2024-05-01"
    assert row["option_info"] == "opt"
    assert row["unique_option_info"] == "sunroof"
    assert row["diag_info"] == "diag"


def test_settings_crawl_key_overrides_env(app):
    with app.app_context():
        app.config["CRAWL_API_KEY"] = "from-env"
        app.config["CRAWL_API_URL"] = "https://env.example"
        set_setting("crawl_api_key", "from-db")
        set_setting("crawl_api_url", "https://db.example")
        url, key = crawl_credentials()
        assert url == "https://db.example"
        assert key == "from-db"
        assert crawl_key_configured() is True


def test_next_sunday_midnight_kst_is_monday_00():
    seoul = ZoneInfo("Asia/Seoul")
    # 2026-09-13 is Sunday
    now = datetime(2026, 9, 13, 21, 0, tzinfo=seoul)
    nxt = next_sunday_midnight_kst(now)
    assert nxt.tzinfo == seoul
    assert nxt.weekday() == 0
    assert nxt.hour == 0
    assert nxt.minute == 0
    assert nxt.date().isoformat() == "2026-09-14"


def test_settings_page_saves_keys_and_manual_collect(client, app, monkeypatch):
    with app.app_context():
        seed_admin_user()

    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    page = client.get("/settings")
    assert page.status_code == 200
    assert "Crawl API".encode() in page.data or "크롤".encode() in page.data
    assert "발급".encode() in page.data

    saved = client.post(
        "/settings",
        data={
            "action": "save_crawl",
            "crawl_api_url": "https://crawl.wecarmobility.co.kr",
            "crawl_api_key": "secret-crawl-key",
        },
        follow_redirects=True,
    )
    assert saved.status_code == 200
    with app.app_context():
        assert crawl_credentials()[1] == "secret-crawl-key"

    items = [
        {
            "id": 3,
            "car_import_yn": "N",
            "site_type": "encar",
            "site_id": "manual-1",
            "car_no": "12가3333",
            "car_year": "2021",
            "car_km": "1",
            "car_price": "900",
            "car_maker": "기아",
            "car_model": "K5",
            "car_fuel": "가솔린",
            "url_link": "https://example.com/3",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
    ]
    monkeypatch.setattr(
        "apps.services.import_crawl.iter_crawling_rows",
        lambda **_kwargs: items,
    )
    collected = client.post(
        "/settings",
        data={"action": "collect"},
        follow_redirects=True,
    )
    assert collected.status_code == 200
    assert "작업".encode() in collected.data
    with app.app_context():
        job = consume_queued_collect()
        assert job is not None
        assert job.status == "completed"
        row = db.session.execute(
            db.select(Vehicle).filter_by(site_id="manual-1")
        ).scalar_one()
        assert row.car_model == "K5"
