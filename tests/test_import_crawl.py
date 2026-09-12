from apps.extensions import db
from apps.models import Vehicle
from apps.models import ImportJob
from apps.services.crawl_client import (
    CrawlHttpError,
    _get_with_retry,
    iter_crawling_rows,
    parse_retry_after,
    retry_wait_seconds,
)
from apps.services.import_crawl import consume_queued_collect, import_from_crawl
from apps.services.settings import CRAWL_COLLECT_NOW, get_setting, set_setting


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

    sleeps = []
    rows = list(
        iter_crawling_rows(
            base_url="https://crawl.example.test",
            api_key="k",
            limit=2,
            http_get=http_get,
            page_delay=1,
            sleep=sleeps.append,
        )
    )
    assert [r["id"] for r in rows] == [1, 2, 3]
    assert any("offset=2" in u for u in calls)
    assert sleeps[0] == 1
    assert all(s == 1 for s in sleeps)


def test_parse_retry_after_and_default_wait():
    assert parse_retry_after({"Retry-After": "15"}) == 15
    assert parse_retry_after({}) is None
    assert retry_wait_seconds(RuntimeError("crawl API HTTP 429: x"), attempt=0) == 60
    assert retry_wait_seconds(RuntimeError("crawl API HTTP 429: x"), attempt=1) == 120
    err = CrawlHttpError(429, "slow", retry_after=7)
    assert retry_wait_seconds(err, attempt=0) == 7


def test_get_with_retry_recovers_from_429():
    calls = {"n": 0}

    def flaky(_url, _headers):
        calls["n"] += 1
        if calls["n"] < 3:
            raise CrawlHttpError(429, "Too many requests", retry_after=None)
        return {"ok": True}

    sleeps = []
    page = _get_with_retry(flaky, "https://x", {}, sleep=sleeps.append)
    assert page == {"ok": True}
    assert calls["n"] == 3
    assert sleeps == [60, 120]


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


def test_replace_import_bulk_inserts_without_keeping_stale_rows(app):
    with app.app_context():
        db.session.add_all(
            [
                Vehicle(site_type="encar", site_id="stale-a", car_price=10),
                Vehicle(site_type="kb", site_id="stale-b", car_price=20),
            ]
        )
        db.session.commit()
        job = import_from_crawl(
            source="cli",
            fetch_rows=lambda: [
                _item(id=11, site_id="n1", car_no="12가1001", car_price="1100"),
                _item(id=12, site_id="n2", car_no="12가1002", car_price="1200"),
                _item(id=12, site_id="n2", car_no="12가1002", car_price="1250"),
            ],
            replace=True,
        )
        assert job.status == "completed"
        assert job.saved_rows == 2
        ids = {
            v.site_id: v.car_price
            for v in db.session.execute(db.select(Vehicle)).scalars()
        }
        assert ids == {"n1": 1100, "n2": 1250}


def test_replace_keeps_existing_rows_if_crawl_fetch_fails(app):
    with app.app_context():
        db.session.add(
            Vehicle(site_type="encar", site_id="keep-me", car_no="12가0001", car_price=100)
        )
        db.session.commit()

        def boom():
            raise RuntimeError("crawl API HTTP 429: Too many requests")
            yield

        try:
            import_from_crawl(source="cli", fetch_rows=boom, replace=True)
        except RuntimeError as exc:
            assert "429" in str(exc)
        else:
            raise AssertionError("expected crawl 429")

        left = db.session.execute(db.select(Vehicle)).scalars().all()
        assert len(left) == 1
        assert left[0].site_id == "keep-me"


def test_collect_post_queues_without_hitting_crawl_api(client, app, monkeypatch):
    from apps.cli import seed_admin_user

    called = {"n": 0}

    def boom(**_kwargs):
        called["n"] += 1
        raise RuntimeError("should not call crawl API from the web request")

    monkeypatch.setattr("apps.services.import_crawl.iter_crawling_rows", boom)
    with app.app_context():
        seed_admin_user()
        set_setting("crawl_api_key", "k")

    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    r = client.post("/settings", data={"action": "collect"}, follow_redirects=True)
    assert r.status_code == 200
    assert called["n"] == 0
    body = r.data.decode()
    assert "예약" in body or "대기" in body
    with app.app_context():
        assert get_setting(CRAWL_COLLECT_NOW) == "1"


def test_consume_queued_collect_imports_and_clears_flag(app):
    with app.app_context():
        set_setting(CRAWL_COLLECT_NOW, "1")
        job = consume_queued_collect(
            fetch_rows=lambda: [_item(id=8, site_id="q1", car_no="12가8001", car_price="1300")]
        )
        assert job is not None
        assert job.status == "completed"
        assert job.saved_rows == 1
        assert get_setting(CRAWL_COLLECT_NOW) is None


def test_import_from_crawl_refuses_second_running_job(app):
    with app.app_context():
        db.session.add(
            ImportJob(
                source="web",
                filename="manual",
                status="running",
            )
        )
        db.session.commit()
        try:
            import_from_crawl(
                source="cli",
                fetch_rows=lambda: [_item(id=9, site_id="x", car_no="12가9001", car_price="1400")],
            )
        except RuntimeError as exc:
            assert "이미 수집" in str(exc)
        else:
            raise AssertionError("expected running lock")


def test_upload_post_queues_then_scheduler_syncs(client, app, monkeypatch):
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
    with app.app_context():
        assert get_setting(CRAWL_COLLECT_NOW) == "1"
        job = consume_queued_collect()
        assert job.status == "completed"
        cars = db.session.execute(db.select(Vehicle)).scalars().all()
        assert len(cars) == 1
        assert cars[0].site_id == "web-1"
        assert cars[0].car_price == 2100
