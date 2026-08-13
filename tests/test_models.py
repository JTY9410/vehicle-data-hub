from apps.extensions import db
from apps.models import Vehicle


def test_vehicle_unique_site(app):
    with app.app_context():
        v1 = Vehicle(site_type="encar", site_id="1", car_no="12가3456", car_price=1000)
        v2 = Vehicle(site_type="encar", site_id="1", car_no="12가3457", car_price=2000)
        db.session.add(v1)
        db.session.commit()
        db.session.add(v2)
        try:
            db.session.commit()
            raised = False
        except Exception:
            db.session.rollback()
            raised = True
        assert raised
