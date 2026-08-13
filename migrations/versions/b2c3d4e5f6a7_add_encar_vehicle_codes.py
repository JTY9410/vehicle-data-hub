"""add encar vehicle code hierarchy tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-13

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicle_maker",
        sa.Column("maker_no", sa.String(length=32), primary_key=True),
        sa.Column("maker_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
    )
    op.create_index("ix_vehicle_maker_maker_name", "vehicle_maker", ["maker_name"])

    op.create_table(
        "vehicle_model",
        sa.Column("model_no", sa.String(length=32), primary_key=True),
        sa.Column("maker_no", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
    )
    op.create_index("ix_vehicle_model_maker_no", "vehicle_model", ["maker_no"])

    op.create_table(
        "vehicle_model_detail",
        sa.Column("mdetail_no", sa.String(length=32), primary_key=True),
        sa.Column("model_no", sa.String(length=32), nullable=True),
        sa.Column("mdetail_name", sa.String(length=256), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
        sa.Column("st_year", sa.Integer(), nullable=True),
        sa.Column("ed_year", sa.Integer(), nullable=True),
    )
    op.create_index("ix_vehicle_model_detail_model_no", "vehicle_model_detail", ["model_no"])

    op.create_table(
        "vehicle_grade",
        sa.Column("grade_no", sa.String(length=32), primary_key=True),
        sa.Column("mdetail_no", sa.String(length=32), nullable=True),
        sa.Column("grade_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
    )
    op.create_index("ix_vehicle_grade_mdetail_no", "vehicle_grade", ["mdetail_no"])

    op.create_table(
        "vehicle_grade_detail",
        sa.Column("gdetail_no", sa.String(length=32), primary_key=True),
        sa.Column("grade_no", sa.String(length=32), nullable=True),
        sa.Column("gdetail_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
    )
    op.create_index("ix_vehicle_grade_detail_grade_no", "vehicle_grade_detail", ["grade_no"])

    with op.batch_alter_table("vehicles") as batch:
        batch.add_column(sa.Column("maker_no", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("model_no", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("mdetail_no", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("grade_no", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("gdetail_no", sa.String(length=32), nullable=True))
        batch.create_index("ix_vehicles_maker_no", ["maker_no"])
        batch.create_index("ix_vehicles_model_no", ["model_no"])
        batch.create_index("ix_vehicles_mdetail_no", ["mdetail_no"])
        batch.create_index("ix_vehicles_grade_no", ["grade_no"])
        batch.create_index("ix_vehicles_gdetail_no", ["gdetail_no"])


def downgrade():
    with op.batch_alter_table("vehicles") as batch:
        batch.drop_index("ix_vehicles_gdetail_no")
        batch.drop_index("ix_vehicles_grade_no")
        batch.drop_index("ix_vehicles_mdetail_no")
        batch.drop_index("ix_vehicles_model_no")
        batch.drop_index("ix_vehicles_maker_no")
        batch.drop_column("gdetail_no")
        batch.drop_column("grade_no")
        batch.drop_column("mdetail_no")
        batch.drop_column("model_no")
        batch.drop_column("maker_no")
    op.drop_table("vehicle_grade_detail")
    op.drop_table("vehicle_grade")
    op.drop_table("vehicle_model_detail")
    op.drop_table("vehicle_model")
    op.drop_table("vehicle_maker")
