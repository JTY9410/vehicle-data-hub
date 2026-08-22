"""composite index for car_fuel + id sort

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-22

"""
from alembic import op


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vehicles_car_fuel_id ON vehicles (car_fuel, id)"
    )


def downgrade():
    op.drop_index("ix_vehicles_car_fuel_id", table_name="vehicles")
