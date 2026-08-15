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
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicles_maker_no_id ON vehicles (maker_no, id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicles_model_no_id ON vehicles (model_no, id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vehicles_scraped_at_id ON vehicles (scraped_at, id)"
    )


def downgrade():
    op.drop_index("ix_vehicles_scraped_at_id", table_name="vehicles")
    op.drop_index("ix_vehicles_model_no_id", table_name="vehicles")
    op.drop_index("ix_vehicles_maker_no_id", table_name="vehicles")
