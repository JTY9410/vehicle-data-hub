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

        if os.environ.get("VERCEL"):
            with app.app_context():
                db.create_all()
                from apps.cli import seed_admin_user

                seed_admin_user()

        return app
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
        fallback = Flask(__name__)

        @fallback.get("/healthz")
        def healthz_boot_error():
            from flask import jsonify

            return jsonify(status="boot_error", detail=err), 500

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
