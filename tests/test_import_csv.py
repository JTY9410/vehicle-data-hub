from pathlib import Path

from apps.extensions import db
from apps.models import Vehicle
from apps.services.import_csv import import_csv_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


def test_import_filters_and_upsert(app):
    with app.app_context():
        job = import_csv_file(FIXTURE, source="cli")
        assert job.status == "completed"
        assert job.saved_rows >= 1
        assert job.rejected_rows >= 2
        cars = db.session.execute(db.select(Vehicle)).scalars().all()
        assert all("하" not in (c.car_no or "") for c in cars)
        assert all(c.car_price is not None and 0 < c.car_price < 9999 for c in cars)
        upserted = db.session.execute(
            db.select(Vehicle).filter_by(site_type="encar", site_id="site-upsert")
        ).scalar_one()
        assert upserted.car_price == 2200
        assert upserted.car_color == "검정"
