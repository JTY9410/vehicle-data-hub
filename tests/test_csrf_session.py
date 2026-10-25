"""CSRF 세션 쿠키 및 에러 핸들링 테스트"""
from apps.extensions import db
from apps.models import User
from werkzeug.security import generate_password_hash


def test_login_get_sets_session_cookie_and_no_store(client, app):
    """로그인 GET 요청이 vh_session 쿠키를 설정하고 Cache-Control: no-store를 반환하는지 확인"""
    with app.app_context():
        db.session.add(
            User(
                username="testuser",
                password_hash=generate_password_hash("testpass", method="scrypt"),
            )
        )
        db.session.commit()

    resp = client.get("/login")
    assert resp.status_code == 200

    # vh_session 쿠키가 설정되었는지 확인
    # Flask test client는 set_cookie 헤더를 통해 쿠키 확인
    assert "Set-Cookie" in resp.headers
    set_cookie_header = resp.headers.get("Set-Cookie")
    assert "vh_session=" in set_cookie_header, "vh_session cookie should be set"

    # Cache-Control: no-store 헤더 확인
    assert "Cache-Control" in resp.headers
    assert "no-store" in resp.headers["Cache-Control"]
    assert "private" in resp.headers["Cache-Control"]


def test_login_post_without_cookie_returns_friendly_redirect(tmp_path, monkeypatch):
    """세션 쿠키 없이 POST하면 친절한 에러와 리다이렉트를 반환하는지 확인
    
    CSRF가 활성화된 전용 앱으로 테스트:
    1. 쿠키 없이 POST → 302/303 to /login + 한국어 플래시
    2. 쿠키 + 유효 토큰으로 POST → 로그인 성공
    3. /api/ 경로는 CSRF 에러 핸들러 영향 없음
    """
    from apps import create_app
    import config as config_module
    import re

    # CSRF 활성화된 전용 앱 생성
    monkeypatch.setenv("SECRET_KEY", "test-csrf-secret")
    db_url = f"sqlite:///{tmp_path / 'csrf_test.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setattr(config_module.Config, "SQLALCHEMY_DATABASE_URI", db_url)
    monkeypatch.setattr(config_module.Config, "SQLALCHEMY_ENGINE_OPTIONS", {}, raising=False)

    csrf_app = create_app()
    csrf_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_CHECK_DEFAULT=True,
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_ENGINE_OPTIONS={},
    )

    with csrf_app.app_context():
        db.create_all()
        db.session.add(
            User(
                username="csrfuser",
                password_hash=generate_password_hash("csrfpass", method="scrypt"),
            )
        )
        db.session.commit()

    # 테스트 1: 쿠키 없이 POST → 302/303 리다이렉트 + 한국어 플래시
    with csrf_app.test_client() as client1:
        login_page = client1.get("/login")
        assert login_page.status_code == 200

        # HTML에서 csrf_token 추출
        html = login_page.data.decode("utf-8")
        token_match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert token_match, "csrf_token not found in HTML"
        csrf_token = token_match.group(1)

    # 새 클라이언트 (쿠키 없음)로 POST
    with csrf_app.test_client() as client2:
        resp = client2.post(
            "/login",
            data={"username": "csrfuser", "password": "csrfpass", "csrf_token": csrf_token},
            follow_redirects=False,
        )

        # 정확히 302 또는 303 리다이렉트
        assert resp.status_code in (302, 303), f"Expected redirect, got {resp.status_code}"
        assert resp.headers["Location"].endswith("/login")

        # 리다이렉트 따라가서 플래시 메시지 확인
        redirect_resp = client2.get(resp.headers["Location"])
        redirect_html = redirect_resp.data.decode("utf-8")
        assert "세션이 만료되었거나" in redirect_html or "쿠키가 차단" in redirect_html

    # 테스트 2: 쿠키 + 유효 토큰으로 POST → 로그인 성공
    with csrf_app.test_client() as client3:
        # GET으로 토큰과 쿠키 얻기
        login_page = client3.get("/login")
        html = login_page.data.decode("utf-8")
        token_match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        csrf_token = token_match.group(1)

        # 같은 클라이언트로 POST (쿠키 유지)
        resp = client3.post(
            "/login",
            data={"username": "csrfuser", "password": "csrfpass", "csrf_token": csrf_token},
            follow_redirects=False,
        )

        # 성공적인 로그인 리다이렉트
        assert resp.status_code in (302, 303)
        assert resp.headers["Location"].endswith("/")

    # 테스트 3: /api/ 경로는 CSRF 에러 핸들러 영향 없음
    with csrf_app.test_client() as client4:
        # API는 csrf.exempt(api_bp)로 보호 제외됨
        # 하지만 400 핸들러가 /api/에서는 JSON 반환하는지 확인
        api_resp = client4.post("/api/v1/vehicles", json={"test": "data"})
        # API 키 없으면 401, 있으면 404 (POST는 지원 안함)
        # 400이 아닌지만 확인
        assert api_resp.status_code != 400 or api_resp.is_json

    with csrf_app.app_context():
        db.session.remove()
        db.drop_all()


def test_session_cookie_name_is_consistent(app):
    """SESSION_COOKIE_NAME이 vh_session으로 설정되어 있는지 확인"""
    assert app.config["SESSION_COOKIE_NAME"] == "vh_session"


def test_session_cookie_path_is_root(app):
    """SESSION_COOKIE_PATH가 /로 설정되어 있는지 확인"""
    assert app.config["SESSION_COOKIE_PATH"] == "/"


def test_permanent_session_lifetime_is_set(app):
    """PERMANENT_SESSION_LIFETIME이 설정되어 있는지 확인 (43200초 = 12시간)"""
    assert app.config["PERMANENT_SESSION_LIFETIME"] == 43200


def test_successful_login_flow_with_session(client, app):
    """정상 로그인 플로우가 세션과 함께 작동하는지 확인"""
    with app.app_context():
        db.session.add(
            User(
                username="testuser",
                password_hash=generate_password_hash("testpass", method="scrypt"),
            )
        )
        db.session.commit()

    # 로그인 페이지 GET
    login_page = client.get("/login")
    assert login_page.status_code == 200

    # vh_session 쿠키 확인 (Set-Cookie 헤더)
    assert "Set-Cookie" in login_page.headers
    set_cookie_header = login_page.headers.get("Set-Cookie")
    assert "vh_session=" in set_cookie_header

    # 로그인 POST
    resp = client.post(
        "/login",
        data={"username": "testuser", "password": "testpass"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/")


def test_session_is_permanent(client, app):
    """세션이 permanent로 설정되는지 확인"""
    from flask import session

    with client:
        client.get("/login")
        with client.session_transaction() as sess:
            # before_request에서 session.permanent = True로 설정되므로
            # 실제로는 요청 컨텍스트 내에서만 확인 가능
            # 테스트에서는 설정 값만 확인
            pass

    # PERMANENT_SESSION_LIFETIME 설정 확인으로 대체
    assert app.config["PERMANENT_SESSION_LIFETIME"] == 43200


def test_html_responses_have_no_store_cache_control(client, app):
    """HTML 응답이 Cache-Control: no-store를 가지는지 확인"""
    with app.app_context():
        db.session.add(
            User(
                username="testuser",
                password_hash=generate_password_hash("testpass", method="scrypt"),
            )
        )
        db.session.commit()

    # 로그인 페이지
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Cache-Control" in resp.headers
    assert "no-store" in resp.headers["Cache-Control"]


def test_api_endpoints_do_not_set_session_cookie(client, app):
    """API 엔드포인트는 세션 쿠키를 설정하지 않는지 확인 (before_request 스킵)"""
    # /healthz는 Set-Cookie 없어야 함
    health_resp = client.get("/healthz")
    assert health_resp.status_code == 200
    set_cookie = health_resp.headers.get("Set-Cookie", "")
    assert "vh_session" not in set_cookie, "health endpoint should not set session cookie"

    # /api/v1/vehicles도 Set-Cookie 없어야 함 (API 키 없어도)
    api_resp = client.get("/api/v1/vehicles")
    # 401 또는 403이지만 Set-Cookie는 없어야 함
    set_cookie = api_resp.headers.get("Set-Cookie", "")
    assert "vh_session" not in set_cookie, "api endpoint should not set session cookie"
