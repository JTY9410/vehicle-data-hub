from pathlib import Path

from apps.extensions import db
from apps.models import Vehicle
from apps.services.encar_codes import (
    apply_codes_to_vehicle,
    clear_code_index,
    resolve_csv_to_codes,
)
from apps.services.encar_seed import seed_encar_codes


def _mini_seed(tmp_path: Path):
    clear_code_index()
    (tmp_path / "vehicle_maker.csv").write_text(
        "maker_no,maker_name,sort_no,synced_at\n10055,현대,1,\n", encoding="utf-8"
    )
    (tmp_path / "vehicle_model.csv").write_text(
        "model_no,maker_no,model_name,sort_no\n2001,10055,쏘나타,\n", encoding="utf-8"
    )
    (tmp_path / "vehicle_model_detail.csv").write_text(
        "mdetail_no,model_no,mdetail_name,sort_no,st_year,ed_year\n3001,2001,DN8,,,\n",
        encoding="utf-8",
    )
    (tmp_path / "vehicle_grade.csv").write_text(
        "grade_no,mdetail_no,grade_name,sort_no\n4001,3001,가솔린 2.0,\n", encoding="utf-8"
    )
    (tmp_path / "vehicle_grade_detail.csv").write_text(
        "gdetail_no,grade_no,gdetail_name,sort_no\n5001,4001,인스퍼레이션,\n", encoding="utf-8"
    )


def test_seed_and_resolve_encar_codes(app, tmp_path):
    _mini_seed(tmp_path)
    with app.app_context():
        counts = seed_encar_codes(tmp_path)
        assert counts["makers"] == 1
        assert counts["models"] == 1
        codes = resolve_csv_to_codes(
            car_maker="현대",
            car_model="쏘나타",
            car_submodel="DN8",
            car_grade="가솔린 2.0",
            car_subgrade="인스퍼레이션",
        )
        assert codes["maker_no"] == "10055"
        assert codes["model_no"] == "2001"
        assert codes["mdetail_no"] == "3001"
        assert codes["grade_no"] == "4001"
        assert codes["gdetail_no"] == "5001"

        v = Vehicle(
            site_type="encar",
            site_id="c1",
            car_maker="현대",
            car_model="쏘나타",
            car_submodel="DN8",
            car_grade="가솔린 2.0",
            car_subgrade="인스퍼레이션",
            car_price=2000,
        )
        apply_codes_to_vehicle(v)
        db.session.add(v)
        db.session.commit()
        assert v.maker_no == "10055"
        assert v.gdetail_no == "5001"


def test_maker_alias_renault(app, tmp_path):
    (tmp_path / "vehicle_maker.csv").write_text(
        "maker_no,maker_name,sort_no,synced_at\n1,르노(삼성),1,\n", encoding="utf-8"
    )
    (tmp_path / "vehicle_model.csv").write_text(
        "model_no,maker_no,model_name,sort_no\n", encoding="utf-8"
    )
    (tmp_path / "vehicle_model_detail.csv").write_text(
        "mdetail_no,model_no,mdetail_name,sort_no,st_year,ed_year\n", encoding="utf-8"
    )
    (tmp_path / "vehicle_grade.csv").write_text(
        "grade_no,mdetail_no,grade_name,sort_no\n", encoding="utf-8"
    )
    (tmp_path / "vehicle_grade_detail.csv").write_text(
        "gdetail_no,grade_no,gdetail_name,sort_no\n", encoding="utf-8"
    )
    with app.app_context():
        seed_encar_codes(tmp_path)
        codes = resolve_csv_to_codes(
            car_maker="르노코리아(삼성)",
            car_model=None,
            car_submodel=None,
            car_grade=None,
            car_subgrade=None,
        )
        assert codes["maker_no"] == "1"

        v = Vehicle(
            site_type="encar",
            site_id="alias-1",
            car_maker="르노코리아(삼성)",
            car_price=1000,
        )
        apply_codes_to_vehicle(v)
        assert v.maker_no == "1"
        assert v.car_maker == "르노(삼성)"
