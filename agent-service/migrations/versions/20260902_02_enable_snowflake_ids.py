"""用户与项目主键切换为雪花 ID。

Revision ID: 20260902_02
Revises: 20260902_01
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_02"
down_revision: str | Sequence[str] | None = "20260902_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_project_file_project",
        "pm_project_file",
        type_="foreignkey",
    )
    op.drop_constraint("fk_project_owner", "pm_project", type_="foreignkey")
    op.alter_column(
        "pm_project",
        "id",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        autoincrement=False,
    )
    op.alter_column(
        "pm_user",
        "id",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        autoincrement=False,
    )
    op.create_foreign_key(
        "fk_project_owner",
        "pm_project",
        "pm_user",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_project_file_project",
        "pm_project_file",
        "pm_project",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_project_file_project",
        "pm_project_file",
        type_="foreignkey",
    )
    op.drop_constraint("fk_project_owner", "pm_project", type_="foreignkey")
    op.alter_column(
        "pm_user",
        "id",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        autoincrement=True,
    )
    op.alter_column(
        "pm_project",
        "id",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        autoincrement=True,
    )
    op.create_foreign_key(
        "fk_project_owner",
        "pm_project",
        "pm_user",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_project_file_project",
        "pm_project_file",
        "pm_project",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
