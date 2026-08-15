"""composite indexes for vehicle filter + id sort

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-15

"""
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_vehicles_maker_no_id",
        "vehicles",
        ["maker_no", "id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicles_model_no_id",
        "vehicles",
        ["model_no", "id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicles_scraped_at_id",
        "vehicles",
        ["scraped_at", "id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_vehicles_scraped_at_id", table_name="vehicles")
    op.drop_index("ix_vehicles_model_no_id", table_name="vehicles")
    op.drop_index("ix_vehicles_maker_no_id", table_name="vehicles")
