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

    from apps.routes.health import bp as health_bp

    app.register_blueprint(health_bp)
    return app
