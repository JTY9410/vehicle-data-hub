from pathlib import Path

from flask import Flask

from apps.extensions import csrf, db, login_manager, migrate


def create_app(config_object="config.Config"):
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "static"),
    )
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

    if __import__("os").environ.get("VERCEL"):
        with app.app_context():
            db.create_all()
            from apps.cli import seed_admin_user

            seed_admin_user()

    return app


def _register_cli(app):
    import click

    from apps.cli import seed_admin_user
    from apps.services.import_csv import import_csv_file

    @app.cli.command("seed-admin")
    def seed_admin():
        seed_admin_user()
        click.echo("admin seeded")

    @app.cli.command("import-csv")
    @click.argument("path")
    def import_csv_cmd(path):
        job = import_csv_file(path, source="cli")
        click.echo(
            f"status={job.status} saved={job.saved_rows} "
            f"rejected={job.rejected_rows} skipped={job.skipped_rows}"
        )
