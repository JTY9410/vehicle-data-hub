from pathlib import Path

from flask import Flask

from apps.extensions import csrf, db, login_manager, migrate


def create_app(config_object="config.Config"):
    import os
    import traceback

    root = Path(__file__).resolve().parent.parent
    flask_kwargs = {
        "template_folder": str(root / "templates"),
        "static_folder": str(root / "static"),
    }
    if os.environ.get("VERCEL"):
        flask_kwargs["instance_path"] = "/tmp/flask_instance"

    try:
        app = Flask(__name__, **flask_kwargs)
        app.config.from_object(config_object)

        # ProxyFix: Vercel / TRUST_PROXY / PROXY_FIX_HOPS (nginx 1단 뒤 Mac 서버는 TRUST_PROXY=1)
        _trust = (os.environ.get("TRUST_PROXY") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        _hops_raw = (os.environ.get("PROXY_FIX_HOPS") or "").strip()
        if os.environ.get("VERCEL") or _trust or _hops_raw:
            from werkzeug.middleware.proxy_fix import ProxyFix

            hops = int(_hops_raw or "1")
            if hops < 1:
                hops = 1
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)
            app.config["SESSION_COOKIE_SECURE"] = True
            app.config["REMEMBER_COOKIE_SECURE"] = True
            app.config["PREFERRED_URL_SCHEME"] = "https"
            app.config["WTF_CSRF_SSL_STRICT"] = False

        _require_env = (os.environ.get("REQUIRE_PRODUCTION_ENV") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        ) or _trust
        if (
            _require_env
            and not app.config.get("TESTING")
            and not os.environ.get("VERCEL")
        ):
            missing = []
            sk = (app.config.get("SECRET_KEY") or "").strip()
            if not sk or sk in ("dev-change-me", "change-me-in-production"):
                missing.append("SECRET_KEY")
            if missing:
                raise RuntimeError(
                    "필수 환경변수 누락/기본값: "
                    + ", ".join(missing)
                    + " (.env.example 참고)"
                )

        # SECRET_KEY 기본값 경고 (테스트/디버그·위에서 이미 실패한 경우 제외)
        if (
            app.config.get("SECRET_KEY") == "dev-change-me"
            and not app.config.get("TESTING")
            and not app.config.get("DEBUG")
            and not _require_env
        ):
            import sys
            print(
                "⚠️  WARNING: SECRET_KEY is using the default value 'dev-change-me'. "
                "Set the SECRET_KEY environment variable in production!",
                file=sys.stderr,
            )

        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        upload = Path(app.config["UPLOAD_FOLDER"])
        upload.mkdir(parents=True, exist_ok=True)

        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        login_manager.login_view = "admin.login"
        csrf.init_app(app)

        from apps import models  # noqa: F401
        import apps.auth  # noqa: F401
        from apps.routes.admin import bp as admin_bp
        from apps.routes.api import bp as api_bp
        from apps.routes.health import bp as health_bp

        app.register_blueprint(health_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(api_bp)
        csrf.exempt(api_bp)
        _register_cli(app)

        @app.before_request
        def _make_session_permanent():
            from flask import request, session

            # API와 health 엔드포인트는 세션 설정 스킵 (불필요한 Set-Cookie 방지)
            if request.endpoint and (
                request.endpoint.startswith("api.")
                or request.endpoint.startswith("health.")
            ):
                return
            session.permanent = True

        @app.after_request
        def _security_headers(resp):
            from flask import request

            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            resp.headers.setdefault(
                "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
            )
            # CSRF 토큰이 포함된 HTML 페이지는 캐시 방지 (로그인, 폼 등)
            if (
                request.endpoint
                and not request.endpoint.startswith("api.")
                and not request.endpoint.startswith("health.")
                and resp.status_code == 200
                and resp.content_type
                and "text/html" in resp.content_type
            ):
                resp.headers["Cache-Control"] = "no-store, private"
            return resp

        @app.errorhandler(404)
        def not_found(_err):
            from flask import jsonify, request

            if request.path.startswith("/api/"):
                return jsonify(error="not_found", path=request.path), 404
            # HTML 친화적 안내 (Werkzeug 기본 Not Found 대신)
            return (
                "<!doctype html><html lang=ko><meta charset=utf-8>"
                "<title>페이지 없음</title>"
                "<body style='font-family:sans-serif;padding:2rem'>"
                "<h1>페이지를 찾을 수 없습니다</h1>"
                f"<p>경로: <code>{request.path}</code></p>"
                "<p><a href='/login'>로그인</a> · <a href='/'>대시보드</a></p>"
                "</body></html>"
            ), 404

        @app.errorhandler(400)
        def csrf_error(err):
            from flask import flash, jsonify, redirect, request, url_for

            error_desc = str(err.description) if hasattr(err, "description") else str(err)
            # CSRF 에러인지 확인
            is_csrf = "CSRF" in error_desc or "csrf" in error_desc.lower()

            if request.path.startswith("/api/"):
                return jsonify(error="bad_request", detail=error_desc), 400

            if is_csrf:
                import sys

                # 로그 (토큰 값 자체는 로그하지 않음)
                missing = "missing" in error_desc.lower()
                print(
                    f"CSRF error on {request.method} {request.path}: "
                    f"{'session token missing' if missing else 'token mismatch'}",
                    file=sys.stderr,
                )
                flash(
                    "세션이 만료되었거나 쿠키가 차단되었습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.",
                    "warning",
                )
                # 로그인 페이지로 리다이렉트 (또는 Referer)
                return redirect(url_for("admin.login"))

            # 일반 400 에러
            return (
                "<!doctype html><html lang=ko><meta charset=utf-8>"
                "<title>잘못된 요청</title>"
                "<body style='font-family:sans-serif;padding:2rem'>"
                "<h1>잘못된 요청</h1>"
                f"<p>{error_desc}</p>"
                "<p><a href='/login'>로그인</a> · <a href='/'>대시보드</a></p>"
                "</body></html>"
            ), 400

        # Vercel: cold start에서 create_all/seed 를 돌리면 첫 요청이 수십 초~
        # 이미 Supabase에 스키마·관리자가 있으므로 부트스트랩 생략
        return app
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
        fallback = Flask(__name__)

        @fallback.get("/healthz")
        def healthz_boot_error():
            from flask import jsonify

            return jsonify(status="boot_error", detail=err), 500

        @fallback.get("/")
        @fallback.get("/login")
        def boot_error_page():
            from flask import jsonify

            return (
                jsonify(
                    status="boot_error",
                    message="앱 부팅 실패. /healthz 의 detail 을 확인하세요.",
                    detail=err,
                ),
                500,
            )

        return fallback


def _register_cli(app):
    import click

    from apps.cli import seed_admin_user
    from apps.services.encar_attrs import remap_vehicle_attrs
    from apps.services.encar_codes import remap_all_vehicles, remap_canonical_names
    from apps.services.encar_fuel import remap_vehicle_fuels
    from apps.services.encar_seed import seed_encar_codes
    from apps.services.db_stats import hot_queries
    from apps.services.import_crawl import import_from_crawl
    from apps.services.import_csv import import_csv_file

    @app.cli.command("seed-admin")
    @click.option("--force-password", is_flag=True, help="환경변수 비밀번호로 해시 강제 갱신")
    def seed_admin(force_password):
        seed_admin_user(force_password=force_password)
        click.echo("admin seeded")

    @app.cli.command("seed-encar-codes")
    def seed_encar_codes_cmd():
        counts = seed_encar_codes()
        click.echo(f"encar codes seeded: {counts}")

    @app.cli.command("remap-vehicle-codes")
    def remap_vehicle_codes_cmd():
        result = remap_all_vehicles()
        click.echo(f"remap done: {result}")

    @app.cli.command("remap-fuels")
    def remap_fuels_cmd():
        result = remap_vehicle_fuels()
        click.echo(f"fuel remap: {result}")

    @app.cli.command("remap-attrs")
    def remap_attrs_cmd():
        result = remap_vehicle_attrs()
        click.echo(f"attr remap: {result}")

    @app.cli.command("remap-canonical-names")
    def remap_canonical_names_cmd():
        result = remap_canonical_names()
        click.echo(f"canonical names: {result}")

    @app.cli.command("db-hot-queries")
    def db_hot_queries_cmd():
        rows = hot_queries()
        if not rows:
            click.echo("no pg_stat_statements (or empty)")
            return
        for r in rows:
            click.echo(
                f"{r['pct']}% total={r['total_ms']}ms mean={r['mean_ms']}ms "
                f"calls={r['calls']} | {r['query']}"
            )

    @app.cli.command("import-csv")
    @click.argument("path")
    def import_csv_cmd(path):
        job = import_csv_file(path, source="cli")
        click.echo(
            f"status={job.status} saved={job.saved_rows} "
            f"rejected={job.rejected_rows} skipped={job.skipped_rows}"
        )

    @app.cli.command("import-crawl")
    def import_crawl_cmd():
        job = import_from_crawl(source="cli")
        click.echo(
            f"status={job.status} saved={job.saved_rows} "
            f"rejected={job.rejected_rows} skipped={job.skipped_rows}"
        )
