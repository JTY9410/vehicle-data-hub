from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Vehicle(db.Model):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("site_type", "site_id", name="uq_vehicle_site"),
        Index("ix_vehicle_maker_model", "car_maker", "car_model"),
        Index("ix_vehicle_price", "car_price"),
        Index("ix_vehicle_scraped_at", "scraped_at"),
        Index("ix_vehicle_car_no", "car_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)
    site_type: Mapped[str] = mapped_column(String(32), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    car_no: Mapped[str | None] = mapped_column(String(32))
    car_year: Mapped[str | None] = mapped_column(String(64))
    car_km: Mapped[int | None] = mapped_column(Integer)
    car_price: Mapped[int | None] = mapped_column(Integer)
    car_maker: Mapped[str | None] = mapped_column(String(64))
    car_model: Mapped[str | None] = mapped_column(String(128))
    car_submodel: Mapped[str | None] = mapped_column(String(128))
    car_grade: Mapped[str | None] = mapped_column(String(128))
    car_subgrade: Mapped[str | None] = mapped_column(String(128))
    car_fuel: Mapped[str | None] = mapped_column(String(32))
    car_mission: Mapped[str | None] = mapped_column(String(32))
    car_color: Mapped[str | None] = mapped_column(String(32))
    car_location: Mapped[str | None] = mapped_column(String(64))
    car_import_yn: Mapped[str | None] = mapped_column(String(8))
    car_cc: Mapped[str | None] = mapped_column(String(32))
    car_type: Mapped[str | None] = mapped_column(String(64))
    car_seat: Mapped[str | None] = mapped_column(String(32))
    detail_info: Mapped[str | None] = mapped_column(Text)
    option_info: Mapped[str | None] = mapped_column(Text)
    diag_info: Mapped[str | None] = mapped_column(Text)
    url_link: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Encar vehicle code hierarchy (maker → model → mdetail → grade → gdetail)
    maker_no: Mapped[str | None] = mapped_column(String(32), index=True)
    model_no: Mapped[str | None] = mapped_column(String(32), index=True)
    mdetail_no: Mapped[str | None] = mapped_column(String(32), index=True)
    grade_no: Mapped[str | None] = mapped_column(String(32), index=True)
    gdetail_no: Mapped[str | None] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class VehicleMaker(db.Model):
    __tablename__ = "vehicle_maker"
    maker_no: Mapped[str] = mapped_column(String(32), primary_key=True)
    maker_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sort_no: Mapped[int | None] = mapped_column(Integer)


class VehicleModel(db.Model):
    __tablename__ = "vehicle_model"
    model_no: Mapped[str] = mapped_column(String(32), primary_key=True)
    maker_no: Mapped[str | None] = mapped_column(String(32), index=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_no: Mapped[int | None] = mapped_column(Integer)


class VehicleModelDetail(db.Model):
    __tablename__ = "vehicle_model_detail"
    mdetail_no: Mapped[str] = mapped_column(String(32), primary_key=True)
    model_no: Mapped[str | None] = mapped_column(String(32), index=True)
    mdetail_name: Mapped[str] = mapped_column(String(256), nullable=False)
    sort_no: Mapped[int | None] = mapped_column(Integer)
    st_year: Mapped[int | None] = mapped_column(Integer)
    ed_year: Mapped[int | None] = mapped_column(Integer)


class VehicleGrade(db.Model):
    __tablename__ = "vehicle_grade"
    grade_no: Mapped[str] = mapped_column(String(32), primary_key=True)
    mdetail_no: Mapped[str | None] = mapped_column(String(32), index=True)
    grade_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_no: Mapped[int | None] = mapped_column(Integer)


class VehicleGradeDetail(db.Model):
    __tablename__ = "vehicle_grade_detail"
    gdetail_no: Mapped[str] = mapped_column(String(32), primary_key=True)
    grade_no: Mapped[str | None] = mapped_column(String(32), index=True)
    gdetail_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_no: Mapped[int | None] = mapped_column(Integer)


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportJob(db.Model):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    saved_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
