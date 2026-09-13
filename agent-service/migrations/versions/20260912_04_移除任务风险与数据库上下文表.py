"""移除任务风险与数据库上下文表

Revision ID: 20260912_04
Revises: 20260912_03
Create Date: 2026-09-12 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_04"
down_revision: str | None = "20260912_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """开发阶段数据可丢弃，按外键依赖顺序删除不再使用的表。"""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table_name in (
        "retrieval_evidence_root",
        "retrieval_evidence_node",
        "agent_trusted_chat_evidence",
        "retrieval_chunk",
        "retrieval_index_job",
        "retrieval_evidence_edge",
        "retrieval_document",
        "retrieval_corpus_state",
        "pm_risk_task",
        "pm_risk_evidence",
        "pm_risk_event",
        "pm_task_dependency",
        "pm_task_status_log",
        "pm_risk",
        "pm_task",
        "agent_context_item",
        "context_update_item",
        "agent_context_asset_change",
        "context_update_batch",
        "agent_context_asset",
        "project_analysis_run",
        "agent_action_confirmation_receipt",
        "agent_action_draft",
        "pm_business_command_receipt",
    ):
        if table_name in tables:
            op.drop_table(table_name)
    conversation_columns = {
        column["name"] for column in inspector.get_columns("agent_conversation")
    }
    if "learned_message_id" in conversation_columns:
        op.drop_column("agent_conversation", "learned_message_id")


def downgrade() -> None:
    raise RuntimeError("该开发阶段清理迁移不可逆，请从迁移前备份恢复")
