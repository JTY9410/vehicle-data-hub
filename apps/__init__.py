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

        if os.environ.get("VERCEL"):
            from werkzeug.middleware.proxy_fix import ProxyFix

            # Vercel 엣지 프록시: https / host 인식
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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

        # Vercel: 부팅 시 DB 실패해도 라우트는 유지 (404 fallback 방지)
        if os.environ.get("VERCEL"):
            try:
                with app.app_context():
                    db.create_all()
                    from apps.cli import seed_admin_user

                    seed_admin_user()
            except Exception:  # noqa: BLE001
                app.logger.exception("vercel db bootstrap skipped")

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
    from apps.services.encar_codes import remap_all_vehicles
    from apps.services.encar_seed import seed_encar_codes
    from apps.services.import_csv import import_csv_file

    @app.cli.command("seed-admin")
    def seed_admin():
        seed_admin_user()
        click.echo("admin seeded")

    @app.cli.command("seed-encar-codes")
    def seed_encar_codes_cmd():
        counts = seed_encar_codes()
        click.echo(f"encar codes seeded: {counts}")

    @app.cli.command("remap-vehicle-codes")
    def remap_vehicle_codes_cmd():
        result = remap_all_vehicles()
        click.echo(f"remap done: {result}")

    @app.cli.command("import-csv")
    @click.argument("path")
    def import_csv_cmd(path):
        job = import_csv_file(path, source="cli")
        click.echo(
            f"status={job.status} saved={job.saved_rows} "
            f"rejected={job.rejected_rows} skipped={job.skipped_rows}"
        )
