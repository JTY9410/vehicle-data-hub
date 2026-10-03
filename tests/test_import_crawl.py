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
from apps.services.import_crawl import (
    consume_queued_collect,
    import_from_crawl,
    recover_interrupted_jobs,
    request_manual_collect,
)
from apps.services.settings import (
    CRAWL_COLLECT_NOW,
    CRAWL_COOLDOWN_UNTIL,
    CRAWL_RESUME_ID,
    crawl_cooldown_remaining,
    get_setting,
    set_crawl_cooldown,
    set_setting,
)


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
        if "offset=3" in url:
            return {
                "datas": [_item(id=3, site_id="c")],
                "total": 3,
                "limit": 2,
                "offset": 3,
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
    assert any("offset=3" in u for u in calls)
    assert sleeps[0] == 1
    assert all(s == 1 for s in sleeps)


def test_parse_retry_after_and_default_wait():
    assert parse_retry_after({"Retry-After": "15"}) == 15
    assert parse_retry_after({}) is None
    assert retry_wait_seconds(RuntimeError("crawl API HTTP 429: x"), attempt=0) == 60
    assert retry_wait_seconds(RuntimeError("crawl API HTTP 429: x"), attempt=1) == 120
    err = CrawlHttpError(429, "slow", retry_after=7)
    assert retry_wait_seconds(err, attempt=0) == 7


def test_get_with_retry_does_not_hammer_429_without_retry_after():
    calls = {"n": 0}

    def always_429(_url, _headers):
        calls["n"] += 1
        raise CrawlHttpError(429, "Too many requests", retry_after=None)

    sleeps = []
    try:
        _get_with_retry(always_429, "https://x", {}, sleep=sleeps.append)
    except CrawlHttpError as exc:
        assert "429" in str(exc)
    else:
        raise AssertionError("expected 429")
    assert calls["n"] == 1
    assert sleeps == []


def test_get_with_retry_honors_short_retry_after_once():
    calls = {"n": 0}

    def flaky(_url, _headers):
        calls["n"] += 1
        if calls["n"] < 2:
            raise CrawlHttpError(429, "Too many requests", retry_after=3)
        return {"ok": True}

    sleeps = []
    page = _get_with_retry(flaky, "https://x", {}, sleep=sleeps.append)
    assert page == {"ok": True}
    assert calls["n"] == 2
    assert sleeps == [3]


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


def test_iter_crawling_rows_resumes_from_offset():
    calls = []

    def http_get(url, headers):
        calls.append(url)
        if "offset=10" in url:
            return {"datas": [_item(id=11, site_id="r1")], "total": 11, "limit": 2, "offset": 10}
        return {"datas": [], "total": 11, "limit": 2, "offset": 99}

    rows = list(
        iter_crawling_rows(
            base_url="https://crawl.example.test",
            api_key="k",
            limit=2,
            start_offset=10,
            http_get=http_get,
        )
    )
    assert [r["id"] for r in rows] == [11]
    assert any("offset=10" in u for u in calls)


def test_replace_keeps_existing_if_later_page_fails(app):
    with app.app_context():
        db.session.add(
            Vehicle(site_type="encar", site_id="keep-me", car_no="12가0001", car_price=100)
        )
        db.session.commit()

        def pages():
            yield _item(id=1, site_id="n1", car_no="12가1001", car_price="1100")
            raise RuntimeError("crawl API HTTP 429: Too many requests")

        try:
            import_from_crawl(source="cli", fetch_rows=pages, replace=True)
        except RuntimeError as exc:
            assert "429" in str(exc)
        else:
            raise AssertionError("expected crawl 429")

        left = {
            v.site_id: v.car_price
            for v in db.session.execute(db.select(Vehicle)).scalars()
        }
        assert left["keep-me"] == 100
        assert left["n1"] == 1100


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

    client.post("/login", data={"username": "testadmin", "password": "test-admin-pass"})
    r = client.post("/settings", data={"action": "collect"}, follow_redirects=True)
    assert r.status_code == 200
    assert called["n"] == 0
    body = r.data.decode()
    assert "작업" in body
    assert "예약했습니다" not in body
    with app.app_context():
        job = db.session.execute(
            db.select(ImportJob).order_by(ImportJob.id.desc())
        ).scalars().first()
        assert job is not None
        assert job.status in {"pending", "running"}
        assert get_setting(CRAWL_COLLECT_NOW) == str(job.id)


def test_429_sets_cooldown_and_requeues(app):
    with app.app_context():
        def boom():
            raise RuntimeError("crawl API HTTP 429: Too many requests")
            yield

        try:
            import_from_crawl(source="cli", fetch_rows=boom, replace=True)
        except RuntimeError as exc:
            assert "429" in str(exc)
        else:
            raise AssertionError("expected crawl 429")
        assert crawl_cooldown_remaining() >= 60
        assert get_setting(CRAWL_COLLECT_NOW) == "now"


def test_consume_skips_while_cooldown_active(app):
    with app.app_context():
        set_crawl_cooldown(600)
        set_setting(CRAWL_COLLECT_NOW, "now")
        job = consume_queued_collect(
            fetch_rows=lambda: [_item(id=8, site_id="q1", car_no="12가8001", car_price="1300")]
        )
        assert job is None
        assert get_setting(CRAWL_COLLECT_NOW) == "now"


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


def test_stale_running_job_is_released_so_queue_can_run(app):
    from datetime import timedelta

    from apps.models import utcnow

    with app.app_context():
        db.session.add(
            ImportJob(
                source="web",
                filename="manual",
                status="running",
                processed_rows=0,
                started_at=utcnow() - timedelta(minutes=50),
            )
        )
        db.session.commit()
        set_setting(CRAWL_COLLECT_NOW, "1")
        job = consume_queued_collect(
            fetch_rows=lambda: [_item(id=8, site_id="q2", car_no="12가8002", car_price="1300")]
        )
        assert job is not None
        assert job.status == "completed"
        stale = db.session.execute(
            db.select(ImportJob).where(ImportJob.filename == "manual")
        ).scalar_one()
        assert stale.status == "failed"


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

    client.post("/login", data={"username": "testadmin", "password": "test-admin-pass"})
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


def test_get_with_retry_does_not_repeat_http_500():
    calls = {"n": 0}

    def always_500(_url, _headers):
        calls["n"] += 1
        raise CrawlHttpError(500, "Internal Server Error")

    try:
        _get_with_retry(always_500, "https://x", {}, sleep=lambda _s: None)
    except CrawlHttpError as exc:
        assert exc.code == 500
    else:
        raise AssertionError("expected 500")
    assert calls["n"] == 1


def _server_with_bad_id(ids, bad_id, calls=None):
    from urllib.parse import parse_qs, urlparse

    def http_get(url, _headers):
        q = parse_qs(urlparse(url).query)
        offset, limit = int(q["offset"][0]), int(q["limit"][0])
        if calls is not None:
            calls.append((offset, limit))
        page = [i for i in ids if i >= offset][:limit]
        if bad_id in page:
            raise CrawlHttpError(500, "Internal Server Error")
        return {"datas": [_item(id=i, site_id=f"s{i}") for i in page]}

    return http_get


def test_iter_crawling_rows_shrinks_page_and_skips_bad_row_on_500():
    limits, skipped = [], []
    rows = list(
        iter_crawling_rows(
            base_url="https://crawl.example.test",
            api_key="k",
            limit=4,
            http_get=_server_with_bad_id([1, 2, 3, 4, 5, 6], 3),
            on_limit=limits.append,
            on_skip=skipped.append,
        )
    )
    assert [r["id"] for r in rows] == [1, 2, 4, 5, 6]
    assert skipped == [3]
    assert limits[0] == 1


def test_iter_crawling_rows_gives_up_when_every_request_fails():
    def always_500(_url, _headers):
        raise CrawlHttpError(500, "Internal Server Error")

    skipped = []
    try:
        list(
            iter_crawling_rows(
                base_url="https://crawl.example.test",
                api_key="k",
                limit=1,
                http_get=always_500,
                on_skip=skipped.append,
            )
        )
    except CrawlHttpError as exc:
        assert exc.code == 500
    else:
        raise AssertionError("expected 500")
    assert 0 < len(skipped) <= 20


def test_import_keeps_small_page_limit_across_429_then_completes(app, monkeypatch):
    from apps.services.settings import CRAWL_PAGE_LIMIT

    ids = list(range(1, 9))
    calls = []
    server = _server_with_bad_id(ids, 3, calls)
    state = {"n": 0}

    def limited(url, headers):
        state["n"] += 1
        if state["n"] == 3:
            raise CrawlHttpError(429, "Too many requests")
        return server(url, headers)

    monkeypatch.setattr("apps.services.crawl_client._default_http_get", limited)
    monkeypatch.setattr("apps.services.import_crawl.PAGE_DELAY_SECONDS", 0)
    with app.app_context():
        set_setting("crawl_api_key", "k")
        try:
            import_from_crawl(source="cli", replace=False)
        except RuntimeError as exc:
            assert "429" in str(exc)
        else:
            raise AssertionError("expected 429")
        assert get_setting(CRAWL_PAGE_LIMIT) == "125"
        assert get_setting(CRAWL_COLLECT_NOW) == "now"

        set_setting(CRAWL_COOLDOWN_UNTIL, "")
        calls.clear()
        job = import_from_crawl(source="cli", replace=False)
        assert job.status == "completed"
        assert calls[0][1] == 125
        saved = {
            v.source_id for v in db.session.execute(db.select(Vehicle)).scalars()
        }
        assert saved == {"1", "2", "4", "5", "6", "7", "8"}
        assert get_setting(CRAWL_PAGE_LIMIT) is None
        assert get_setting(CRAWL_RESUME_ID) is None


def test_non_429_failure_requeues_with_cooldown(app):
    with app.app_context():
        set_setting(CRAWL_RESUME_ID, "300")

        def boom():
            raise CrawlHttpError(500, "Internal Server Error")
            yield

        try:
            import_from_crawl(source="cli", fetch_rows=boom, replace=False)
        except RuntimeError as exc:
            assert "500" in str(exc)
        else:
            raise AssertionError("expected 500")
        assert get_setting(CRAWL_RESUME_ID) == "300"
        assert get_setting(CRAWL_COLLECT_NOW) == "now"
        assert crawl_cooldown_remaining() >= 60


def test_manual_collect_catches_up_from_latest_source_id(app):
    with app.app_context():
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="catch-1",
                source_id="500",
                car_no="12가0500",
                car_price=1000,
            )
        )
        db.session.commit()
        set_setting(CRAWL_RESUME_ID, "100")
        job = request_manual_collect()
        assert job.status == "pending"
        assert get_setting(CRAWL_RESUME_ID) == "500"
        assert get_setting(CRAWL_COLLECT_NOW) == str(job.id)


def test_429_keeps_resume_id(app):
    with app.app_context():
        set_setting(CRAWL_RESUME_ID, "220")

        def boom():
            raise RuntimeError("crawl API HTTP 429: Too many requests")
            yield

        try:
            import_from_crawl(source="cli", fetch_rows=boom, replace=True)
        except RuntimeError as exc:
            assert "429" in str(exc)
        else:
            raise AssertionError("expected crawl 429")
        assert get_setting(CRAWL_RESUME_ID) == "220"
        assert crawl_cooldown_remaining() >= 60


def test_get_with_retry_retries_dns_failure():
    calls = {"n": 0}

    def flaky(_url, _headers):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("crawl API 연결 실패: [Errno -3] Temporary failure in name resolution")
        return {"ok": True}

    sleeps = []
    page = _get_with_retry(flaky, "https://x", {}, sleep=sleeps.append)
    assert page == {"ok": True}
    assert calls["n"] == 2
    assert sleeps


def test_recover_interrupted_jobs_requeues_without_cooldown(app):
    with app.app_context():
        db.session.add(ImportJob(source="web", filename="manual", status="running"))
        db.session.commit()
        n = recover_interrupted_jobs()
        assert n == 1
        assert get_setting(CRAWL_COLLECT_NOW) == "now"
        assert crawl_cooldown_remaining() == 0
        assert get_setting(CRAWL_COOLDOWN_UNTIL) is None
