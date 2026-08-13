from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from apps.extensions import db
from apps.models import ApiKey, ImportJob, User, Vehicle
from apps.services.api_keys import create_api_key, revoke_api_key
from apps.services.import_csv import import_csv_file

bp = Blueprint("admin", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.session.execute(
            db.select(User).filter_by(username=username)
        ).scalar_one_or_none()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("admin.dashboard"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


@bp.get("/")
@login_required
def dashboard():
    vehicle_count = db.session.execute(
        db.select(db.func.count()).select_from(Vehicle)
    ).scalar_one()
    jobs = db.session.execute(
        db.select(ImportJob).order_by(ImportJob.id.desc()).limit(10)
    ).scalars().all()
    return render_template(
        "dashboard.html", vehicle_count=vehicle_count, jobs=jobs
    )


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    job = None
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("CSV 파일을 선택하세요.", "warning")
            return redirect(url_for("admin.upload"))
        filename = secure_filename(file.filename)
        if not filename.lower().endswith(".csv"):
            flash("CSV 파일만 업로드할 수 있습니다.", "warning")
            return redirect(url_for("admin.upload"))
        dest = Path(current_app.config["UPLOAD_FOLDER"]) / filename
        file.save(dest)
        job = import_csv_file(dest, source="web", filename=filename)
        flash(
            f"적재 완료: 저장 {job.saved_rows}, 거부 {job.rejected_rows}, 스킵 {job.skipped_rows}",
            "success",
        )
        return redirect(url_for("admin.upload_status", job_id=job.id))
    return render_template("upload.html", job=job)


@bp.get("/upload/<int:job_id>")
@login_required
def upload_status(job_id: int):
    job = db.session.get(ImportJob, job_id)
    if job is None:
        flash("작업을 찾을 수 없습니다.", "warning")
        return redirect(url_for("admin.upload"))
    return render_template("upload.html", job=job)


@bp.get("/upload/<int:job_id>/status")
@login_required
def upload_status_json(job_id: int):
    job = db.session.get(ImportJob, job_id)
    if job is None:
        return jsonify(error="not_found"), 404
    return jsonify(
        id=job.id,
        status=job.status,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        saved_rows=job.saved_rows,
        skipped_rows=job.skipped_rows,
        rejected_rows=job.rejected_rows,
    )


@bp.route("/api-keys", methods=["GET", "POST"])
@login_required
def api_keys():
    plaintext = None
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("키 이름을 입력하세요.", "warning")
        else:
            _row, plaintext = create_api_key(name)
            flash("API 키가 발급되었습니다. 지금만 평문이 표시됩니다.", "success")
    keys = db.session.execute(
        db.select(ApiKey).order_by(ApiKey.id.desc())
    ).scalars().all()
    return render_template("api_keys.html", keys=keys, plaintext=plaintext)


@bp.post("/api-keys/<int:key_id>/revoke")
@login_required
def api_keys_revoke(key_id: int):
    if revoke_api_key(key_id):
        flash("API 키를 비활성화했습니다.", "success")
    else:
        flash("API 키를 찾을 수 없습니다.", "warning")
    return redirect(url_for("admin.api_keys"))
