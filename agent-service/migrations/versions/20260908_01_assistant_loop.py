"""增加会话、学习上下文、报告与调用轨迹。

所有新增业务表由 Alembic 管理。
"""

from alembic import op
import sqlalchemy as sa

revision = "20260908_01"
down_revision = "20260903_02"
branch_labels = None
depends_on = None


def upgrade():
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
        "agent_conversation",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("learned_message_id", sa.BigInteger(), nullable=False),
        sa.Column("active_run_id", sa.BigInteger(), nullable=True),
        sa.Column("busy_until", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["pm_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["pm_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_owner_project",
        "agent_conversation",
        ["user_id", "project_id"],
        unique=False,
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
        "agent_message",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("protocol", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["agent_conversation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_conversation_id",
        "agent_message",
        ["conversation_id", "id"],
        unique=False,
    )
    op.create_table(
        "agent_run",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["agent_conversation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["pm_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["pm_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "operation", "request_key", name="uk_run_request"
        ),
    )
    op.create_index(
        "ix_run_conversation_status",
        "agent_run",
        ["conversation_id", "status"],
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
    op.create_table(
        "pm_report",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("source_versions", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["pm_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["pm_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_project_kind",
        "pm_report",
        ["project_id", "kind", "id"],
        unique=False,
    )


def downgrade():
    op.drop_table("pm_report")
    op.drop_table("agent_context_change")
    op.drop_table("agent_run")
    op.drop_table("agent_message")
    op.drop_table("agent_context_entry")
    op.drop_table("agent_conversation")
    op.drop_table("agent_context_scope")
