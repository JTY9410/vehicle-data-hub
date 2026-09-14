"""vehicles korean alias columns for crawl fields

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-14

"""
from alembic import op
import sqlalchemy as sa


revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vehicles", sa.Column("색상", sa.String(length=32), nullable=True))
    op.add_column("vehicles", sa.Column("미션", sa.String(length=32), nullable=True))
    op.add_column("vehicles", sa.Column("차종", sa.String(length=64), nullable=True))
    op.add_column("vehicles", sa.Column("인승", sa.String(length=32), nullable=True))
    op.add_column(
        "vehicles", sa.Column("성능점검일", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("vehicles", sa.Column("옵션정보", sa.Text(), nullable=True))
    op.add_column("vehicles", sa.Column("유용옵션", sa.Text(), nullable=True))
    op.add_column("vehicles", sa.Column("진단정보", sa.Text(), nullable=True))
    op.execute(
        'UPDATE vehicles SET '
        '"색상" = car_color, '
        '"미션" = car_mission, '
        '"차종" = car_type, '
        '"인승" = car_seat, '
        '"성능점검일" = inspected_at, '
        '"옵션정보" = option_info, '
        '"유용옵션" = unique_option_info, '
        '"진단정보" = diag_info'
    )


def downgrade():
    op.drop_column("vehicles", "진단정보")
    op.drop_column("vehicles", "유용옵션")
    op.drop_column("vehicles", "옵션정보")
    op.drop_column("vehicles", "성능점검일")
    op.drop_column("vehicles", "인승")
    op.drop_column("vehicles", "차종")
    op.drop_column("vehicles", "미션")
    op.drop_column("vehicles", "색상")
