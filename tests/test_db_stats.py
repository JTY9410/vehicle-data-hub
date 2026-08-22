from datetime import datetime, timezone

from apps.cli import seed_admin_user
from apps.extensions import db
from apps.models import Vehicle
from apps.services.db_stats import count_stmt_ids, estimate_row_count
from sqlalchemy.orm import load_only


def test_estimate_row_count_sqlite_fallback(app):
    with app.app_context():
        db.session.add(
            Vehicle(site_type="encar", site_id="est-1", car_price=1000)
        )
        db.session.commit()
        assert estimate_row_count("vehicles") == 1


def test_estimate_row_count_rejects_unknown_table(app):
    with app.app_context():
        try:
            estimate_row_count("not_a_table")
            assert False, "expected ValueError"
        except ValueError:
            pass


def test_count_stmt_ids_ignores_load_only(app):
    with app.app_context():
        db.session.add_all(
            [
                Vehicle(
                    site_type="encar",
                    site_id="c-1",
                    car_price=1000,
                    maker_no="10055",
                ),
                Vehicle(
                    site_type="encar",
                    site_id="c-2",
                    car_price=2000,
                    maker_no="10055",
                ),
                Vehicle(
                    site_type="encar",
                    site_id="c-3",
                    car_price=3000,
                    maker_no="10001",
                ),
            ]
        )
        db.session.commit()
        stmt = (
            db.select(Vehicle)
            .options(load_only(Vehicle.id, Vehicle.maker_no))
            .where(Vehicle.maker_no == "10055")
        )
        assert count_stmt_ids(stmt, Vehicle.id) == 2


def test_admin_vehicles_code_filter_orders_by_id(client, app):
    with app.app_context():
        seed_admin_user()
        now = datetime.now(timezone.utc)
        db.session.add(
            Vehicle(
                site_type="encar",
                site_id="ord-1",
                car_price=1000,
                maker_no="10055",
                car_maker="현대",
                car_model="쏘나타",
                scraped_at=now,
            )
        )
        db.session.commit()
    client.post("/login", data={"username": "wecar", "password": "1004wecar"})
    r = client.get("/vehicles?maker_no=10055")
    assert r.status_code == 200
    assert "쏘나타".encode() in r.data
