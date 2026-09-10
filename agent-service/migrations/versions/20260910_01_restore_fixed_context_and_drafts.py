"""恢复固定上下文并把显式学习草稿迁移到 MySQL。

Revision ID: 20260910_01
Revises: 20260909_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260910_01"
down_revision = "20260909_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_learning_draft",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "state IN ('pending','updating','partial','applied','discarded')",
            name="ck_learning_draft_state",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_draft_owner_project_state",
        "agent_learning_draft",
        ["user_id", "project_id", "state", "id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_draft_conversation",
        "agent_learning_draft",
        ["conversation_id", "id"],
        unique=False,
    )

    # 部署后旧进程无法续租；迁移时立即释放临时运行，不调整历史业务时间。
    op.execute(
        "UPDATE agent_run SET status='failed', error='服务升级中断，运行已释放', "
        "active_scope_key=NULL, lease_until=NULL WHERE status='running'"
    )
    op.execute(
        "UPDATE agent_conversation SET active_run_id=NULL, busy_until=NULL "
        "WHERE active_run_id IS NOT NULL"
    )


def downgrade():
    op.drop_index("ix_learning_draft_conversation", table_name="agent_learning_draft")
    op.drop_index(
        "ix_learning_draft_owner_project_state", table_name="agent_learning_draft"
    )
    op.drop_table("agent_learning_draft")
