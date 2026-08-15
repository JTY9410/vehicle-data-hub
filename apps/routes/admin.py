from pathlib import Path
import os

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
from sqlalchemy.orm import load_only
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from apps.extensions import db
from apps.models import (
    ApiKey,
    ImportJob,
    User,
    Vehicle,
    VehicleGrade,
    VehicleGradeDetail,
    VehicleMaker,
    VehicleModel,
    VehicleModelDetail,
)
from apps.services.api_keys import create_api_key, reveal_api_key, revoke_api_key
from apps.services.db_stats import count_stmt_ids, estimate_row_count, hot_queries
from apps.services.import_csv import import_csv_file, parse_date_bound

bp = Blueprint("admin", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        try:
            user = db.session.execute(
                db.select(User).filter_by(username=username)
            ).scalar_one_or_none()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect(url_for("admin.dashboard"))
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            flash(f"로그인 처리 중 오류: {exc}", "danger")
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


@bp.get("/")
@login_required
def dashboard():
    vehicle_count = _estimate_vehicle_count()
    jobs = db.session.execute(
        db.select(ImportJob).order_by(ImportJob.id.desc()).limit(10)
    ).scalars().all()
    return render_template(
        "dashboard.html", vehicle_count=vehicle_count, jobs=jobs
    )


@bp.get("/dashboard")
@login_required
def dashboard_alias():
    return redirect(url_for("admin.dashboard"))


@bp.post("/reset-data")
@login_required
def reset_data():
    confirm = (request.form.get("confirm") or "").strip()
    if confirm != "DELETE":
        flash('초기화하려면 확인란에 DELETE 를 입력하세요.', "warning")
        return redirect(url_for("admin.dashboard"))
    deleted_vehicles = db.session.execute(db.delete(Vehicle)).rowcount or 0
    deleted_jobs = db.session.execute(db.delete(ImportJob)).rowcount or 0
    db.session.commit()
    flash(
        f"데이터 초기화 완료: 차량 {deleted_vehicles:,}건, 적재이력 {deleted_jobs:,}건 삭제 "
        "(API 키·관리자 계정은 유지)",
        "success",
    )
    return redirect(url_for("admin.dashboard"))


def _valid_text(column):
    return db.and_(
        column.is_not(None),
        column != "",
        column != "NULL",
    )


def _estimate_vehicle_count() -> int:
    return estimate_row_count("vehicles")


_LIST_LOAD = load_only(
    Vehicle.id,
    Vehicle.maker_no,
    Vehicle.model_no,
    Vehicle.mdetail_no,
    Vehicle.grade_no,
    Vehicle.gdetail_no,
    Vehicle.car_maker,
    Vehicle.car_model,
    Vehicle.car_submodel,
    Vehicle.car_grade,
    Vehicle.car_subgrade,
    Vehicle.car_year,
    Vehicle.car_price,
    Vehicle.car_no,
    Vehicle.scraped_at,
    Vehicle.url_link,
)


@bp.get("/vehicles")
@login_required
def vehicles():
    maker_no = (request.args.get("maker_no") or "").strip()
    model_no = (request.args.get("model_no") or "").strip()
    grade_no = (request.args.get("grade_no") or "").strip()
    gdetail_no = (request.args.get("gdetail_no") or "").strip()
    saved_from = (request.args.get("saved_from") or "").strip()
    saved_to = (request.args.get("saved_to") or "").strip()
    # legacy name filters still accepted
    maker = (request.args.get("maker") or "").strip()
    model = (request.args.get("model") or "").strip()
    subgrade = (request.args.get("subgrade") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    per_page = request.args.get("per_page", 100, type=int) or 100
    if per_page not in (50, 100, 200, 500):
        per_page = 100
    # Vercel 서버리스: 큰 페이지는 HTML/JSON이 4.5MB를 넘기면 413
    if os.environ.get("VERCEL") and per_page > 50:
        per_page = 50

    saved_from_dt = parse_date_bound(saved_from, end_of_day=False)
    saved_to_dt = parse_date_bound(saved_to, end_of_day=True)

    filtered = bool(
        maker_no
        or model_no
        or grade_no
        or gdetail_no
        or maker
        or model
        or subgrade
        or saved_from_dt
        or saved_to_dt
    )

    # 개별 쿼리가 길면 전체 함수가 응답 없이 끊김 → DB 쪽 상한
    try:
        db.session.execute(db.text("SET LOCAL statement_timeout = '12000'"))
    except Exception:  # noqa: BLE001
        db.session.rollback()

    total_all = _estimate_vehicle_count()

    makers = db.session.execute(
        db.select(VehicleMaker).order_by(VehicleMaker.maker_name)
    ).scalars().all()

    models = []
    if maker_no:
        models = db.session.execute(
            db.select(VehicleModel)
            .where(VehicleModel.maker_no == maker_no)
            .order_by(VehicleModel.model_name)
        ).scalars().all()

    grades = []
    if model_no:
        mdetail_nos = [
            r[0]
            for r in db.session.execute(
                db.select(VehicleModelDetail.mdetail_no).where(
                    VehicleModelDetail.model_no == model_no
                )
            ).all()
        ]
        if mdetail_nos:
            grades = db.session.execute(
                db.select(VehicleGrade)
                .where(VehicleGrade.mdetail_no.in_(mdetail_nos))
                .order_by(VehicleGrade.grade_name)
            ).scalars().all()

    gdetails = []
    if grade_no:
        gdetails = db.session.execute(
            db.select(VehicleGradeDetail)
            .where(VehicleGradeDetail.grade_no == grade_no)
            .order_by(VehicleGradeDetail.gdetail_name)
        ).scalars().all()

    stmt = db.select(Vehicle).options(_LIST_LOAD)
    if maker_no:
        stmt = stmt.where(Vehicle.maker_no == maker_no)
    elif maker:
        stmt = stmt.where(Vehicle.car_maker == maker)
    if model_no:
        stmt = stmt.where(Vehicle.model_no == model_no)
    elif model:
        stmt = stmt.where(Vehicle.car_model == model)
    if grade_no:
        stmt = stmt.where(Vehicle.grade_no == grade_no)
    if gdetail_no:
        stmt = stmt.where(Vehicle.gdetail_no == gdetail_no)
    elif subgrade:
        stmt = stmt.where(Vehicle.car_subgrade == subgrade)
    if saved_from_dt is not None:
        stmt = stmt.where(Vehicle.scraped_at >= saved_from_dt)
    if saved_to_dt is not None:
        stmt = stmt.where(Vehicle.scraped_at <= saved_to_dt)

    if filtered:
        try:
            total = count_stmt_ids(stmt, Vehicle.id)
        except Exception:  # noqa: BLE001
            db.session.rollback()
            try:
                db.session.execute(db.text("SET LOCAL statement_timeout = '12000'"))
            except Exception:  # noqa: BLE001
                db.session.rollback()
            total = total_all
        # 날짜 필터 시 scraped_at 인덱스 활용 (NULLS LAST 금지: PG 풀스캔 유발)
        order = (Vehicle.scraped_at.desc(), Vehicle.id.desc())
    else:
        total = total_all
        # PK 역순이 서버리스에서 가장 빠름
        order = (Vehicle.id.desc(),)

    pages = max((total + per_page - 1) // per_page, 1) if total else 0
    if pages and page > pages:
        page = pages

    rows = db.session.execute(
        stmt.order_by(*order).offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()
    # 통계(reltuples)가 비어 있어도 실제 행이 있으면 목록은 보여 준다
    if rows and total == 0:
        total = max(total_all, len(rows))
        pages = max((total + per_page - 1) // per_page, 1)
    if rows and total_all == 0:
        total_all = total

    return render_template(
        "vehicles.html",
        vehicles=rows,
        code_makers=makers,
        code_models=models,
        code_grades=grades,
        code_gdetails=gdetails,
        maker_no=maker_no,
        model_no=model_no,
        grade_no=grade_no,
        gdetail_no=gdetail_no,
        saved_from=saved_from,
        saved_to=saved_to,
        page=page,
        pages=pages,
        total=total,
        total_all=total_all,
        per_page=per_page,
    )


@bp.get("/db-stats")
@login_required
def db_stats():
    return render_template("db_stats.html", queries=hot_queries())


@bp.get("/api/codes/makers")
@login_required
def code_makers():
    rows = db.session.execute(
        db.select(VehicleMaker).order_by(VehicleMaker.maker_name)
    ).scalars().all()
    return jsonify([{"maker_no": r.maker_no, "maker_name": r.maker_name} for r in rows])


@bp.get("/api/codes/models")
@login_required
def code_models():
    maker_no = (request.args.get("maker_no") or "").strip()
    stmt = db.select(VehicleModel)
    if maker_no:
        stmt = stmt.where(VehicleModel.maker_no == maker_no)
    rows = db.session.execute(stmt.order_by(VehicleModel.model_name)).scalars().all()
    return jsonify([{"model_no": r.model_no, "model_name": r.model_name} for r in rows])


@bp.get("/api/codes/grades")
@login_required
def code_grades():
    model_no = (request.args.get("model_no") or "").strip()
    if not model_no:
        return jsonify([])
    mdetail_nos = [
        r[0]
        for r in db.session.execute(
            db.select(VehicleModelDetail.mdetail_no).where(
                VehicleModelDetail.model_no == model_no
            )
        ).all()
    ]
    if not mdetail_nos:
        return jsonify([])
    rows = db.session.execute(
        db.select(VehicleGrade)
        .where(VehicleGrade.mdetail_no.in_(mdetail_nos))
        .order_by(VehicleGrade.grade_name)
    ).scalars().all()
    # de-dupe by grade_name keeping first grade_no
    seen = set()
    out = []
    for r in rows:
        if r.grade_name in seen:
            continue
        seen.add(r.grade_name)
        out.append({"grade_no": r.grade_no, "grade_name": r.grade_name})
    return jsonify(out)


@bp.get("/api/codes/gdetails")
@login_required
def code_gdetails():
    grade_no = (request.args.get("grade_no") or "").strip()
    if not grade_no:
        return jsonify([])
    rows = db.session.execute(
        db.select(VehicleGradeDetail)
        .where(VehicleGradeDetail.grade_no == grade_no)
        .order_by(VehicleGradeDetail.gdetail_name)
    ).scalars().all()
    return jsonify(
        [{"gdetail_no": r.gdetail_no, "gdetail_name": r.gdetail_name} for r in rows]
    )


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    job = None
    on_vercel = bool(os.environ.get("VERCEL"))
    if request.method == "POST":
        if on_vercel:
            flash(
                "Vercel은 요청 4.5MB 제한이 있어 대용량 CSV를 올릴 수 없습니다. "
                "로컬 Docker에서 flask import-csv 로 적재하세요.",
                "warning",
            )
            return redirect(url_for("admin.upload"))
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
    return render_template("upload.html", job=job, on_vercel=on_vercel)


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
            flash("API 키가 발급되었습니다. 이름을 클릭하면 다시 보고 복사할 수 있습니다.", "success")
    keys = db.session.execute(
        db.select(ApiKey).order_by(ApiKey.id.desc())
    ).scalars().all()
    return render_template("api_keys.html", keys=keys, plaintext=plaintext)


@bp.get("/api-keys/<int:key_id>/reveal")
@login_required
def api_keys_reveal(key_id: int):
    row = db.session.get(ApiKey, key_id)
    if row is None:
        return jsonify(ok=False, message="키를 찾을 수 없습니다."), 404
    raw = reveal_api_key(key_id)
    if not raw:
        return jsonify(
            ok=False,
            name=row.name,
            message="이 키는 발급 당시 원문을 저장하지 않았습니다. 새로 발급하세요.",
        ), 404
    return jsonify(ok=True, name=row.name, key=raw)


@bp.get("/api-keys/docs")
@login_required
def api_docs():
    return render_template("api_docs.html")


@bp.post("/api-keys/<int:key_id>/revoke")
@login_required
def api_keys_revoke(key_id: int):
    if revoke_api_key(key_id):
        flash("API 키를 비활성화했습니다.", "success")
    else:
        flash("API 키를 찾을 수 없습니다.", "warning")
    return redirect(url_for("admin.api_keys"))
