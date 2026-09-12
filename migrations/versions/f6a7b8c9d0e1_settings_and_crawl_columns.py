"""app settings + crawl unique_option_info/inspected_at

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-12

"""
from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("vehicles", sa.Column("unique_option_info", sa.Text(), nullable=True))
    op.add_column(
        "vehicles", sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("vehicles", "inspected_at")
    op.drop_column("vehicles", "unique_option_info")
    op.drop_table("app_settings")
