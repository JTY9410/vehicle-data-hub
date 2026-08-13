import traceback

from flask import Flask, jsonify


def _boot():
    from apps import create_app

    return create_app()


try:
    app = _boot()
except Exception:  # noqa: BLE001
    _err = traceback.format_exc()
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz_boot_error():
        return jsonify(status="boot_error", detail=_err), 500

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return jsonify(status="boot_error", detail=_err), 500
