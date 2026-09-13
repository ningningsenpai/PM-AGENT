"""业务写命令幂等回执

Revision ID: 20260912_03
Revises: 20260912_02
Create Date: 2026-09-12 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_03"
down_revision: str | None = "20260912_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pm_business_command_receipt",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("committed_revision", sa.Integer(), nullable=False),
        sa.Column("result_type", sa.String(length=32), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "committed_revision = base_revision + 1",
            name="ck_business_command_revision_step",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["pm_project.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "actor_user_id",
            "idempotency_key",
            name="uk_business_command_project_actor_idem",
        ),
    )


def downgrade() -> None:
    op.drop_table("pm_business_command_receipt")
