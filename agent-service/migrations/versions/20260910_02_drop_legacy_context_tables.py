"""删除已由固定上下文文件替代的旧 Context 表。

Revision ID: 20260910_02
Revises: 20260910_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260910_02"
down_revision = "20260910_01"
branch_labels = None
depends_on = None


def upgrade():
    # 先删除子表，避免 MySQL 外键阻止旧 Context 表清理。
    op.drop_table("agent_context_change")
    op.drop_table("agent_context_entry")
    op.drop_table("agent_context_scope")


def downgrade():
    # 降级只能恢复表结构，已删除的历史数据需要从升级前备份恢复。
    op.create_table(
        "agent_context_scope",
        sa.Column("scope_key", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_error", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["pm_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["pm_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scope_key"),
    )
    op.create_table(
        "agent_context_entry",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("scope_key", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("canonical_key", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["pm_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scope_key"], ["agent_context_scope.scope_key"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["pm_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_key", "kind", "canonical_key", name="uk_entry_scope_kind_key"
        ),
    )
    op.create_index(
        "ix_entry_scope_status",
        "agent_context_entry",
        ["user_id", "project_id", "status", "expires_at"],
        unique=False,
    )
    op.create_table(
        "agent_context_change",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("entry_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["agent_context_entry.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_change_entry_version",
        "agent_context_change",
        ["entry_id", "version"],
        unique=False,
    )
