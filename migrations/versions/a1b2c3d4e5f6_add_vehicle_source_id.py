"""add vehicle source_id from csv id

Revision ID: a1b2c3d4e5f6
Revises: 19b7a8e43223
Create Date: 2026-08-13

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "19b7a8e43223"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vehicles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_vehicle_source_id", ["source_id"], unique=False)


def downgrade():
    with op.batch_alter_table("vehicles", schema=None) as batch_op:
        batch_op.drop_index("ix_vehicle_source_id")
        batch_op.drop_column("source_id")
