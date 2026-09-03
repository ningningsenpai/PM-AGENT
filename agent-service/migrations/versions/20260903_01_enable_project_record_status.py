"""调整项目记录状态与活动名称唯一约束。

Revision ID: 20260903_01
Revises: 20260902_02
Create Date: 2026-09-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_01"
down_revision: str | Sequence[str] | None = "20260902_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_project_record_status",
        "pm_project",
        type_="check",
    )
    op.alter_column(
        "pm_project",
        "record_status",
        existing_type=sa.String(length=16),
        existing_nullable=False,
        server_default="enabled",
    )
    op.execute(
        sa.text(
            "UPDATE pm_project "
            "SET record_status = CASE record_status "
            "WHEN 'active' THEN 'enabled' "
            "WHEN 'inactive' THEN 'disabled' "
            "ELSE record_status END"
        )
    )
    op.create_check_constraint(
        "ck_project_record_status",
        "pm_project",
        "record_status IN ('enabled', 'disabled')",
    )
    op.add_column(
        "pm_project",
        sa.Column(
            "enabled_project_name",
            sa.String(length=128),
            sa.Computed(
                "CASE WHEN record_status = 'enabled' THEN project_name ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uk_project_owner_enabled_name",
        "pm_project",
        ["owner_user_id", "enabled_project_name"],
    )
    op.drop_constraint(
        "uk_project_owner_name",
        "pm_project",
        type_="unique",
    )


def downgrade() -> None:
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT owner_user_id, project_name "
                "FROM pm_project "
                "GROUP BY owner_user_id, project_name "
                "HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError("存在同一用户的同名项目历史记录，无法恢复旧项目名称唯一约束")

    op.create_unique_constraint(
        "uk_project_owner_name",
        "pm_project",
        ["owner_user_id", "project_name"],
    )
    op.drop_constraint(
        "uk_project_owner_enabled_name",
        "pm_project",
        type_="unique",
    )
    op.drop_column("pm_project", "enabled_project_name")
    op.drop_constraint(
        "ck_project_record_status",
        "pm_project",
        type_="check",
    )
    op.alter_column(
        "pm_project",
        "record_status",
        existing_type=sa.String(length=16),
        existing_nullable=False,
        server_default="active",
    )
    op.execute(
        sa.text(
            "UPDATE pm_project "
            "SET record_status = CASE record_status "
            "WHEN 'enabled' THEN 'active' "
            "WHEN 'disabled' THEN 'inactive' "
            "ELSE record_status END"
        )
    )
    op.create_check_constraint(
        "ck_project_record_status",
        "pm_project",
        "record_status IN ('active', 'inactive')",
    )
