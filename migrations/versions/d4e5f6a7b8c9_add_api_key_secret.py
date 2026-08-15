"""store sealed api key for admin reveal

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-16

"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS key_secret TEXT")


def downgrade():
    op.drop_column("api_keys", "key_secret")
