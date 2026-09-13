"""新增证据节点与可信根注册表

Revision ID: 20260912_02
Revises: 20260912_01
Create Date: 2026-09-12 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_02"
down_revision: str | None = "20260912_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retrieval_evidence_node",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("evidence_ref", sa.String(length=191), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("project_revision", sa.Integer(), nullable=False),
        sa.Column("origin_project_revision", sa.Integer(), nullable=False),
        sa.Column("node_kind", sa.String(length=16), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("authority_kind", sa.String(length=32), nullable=False),
        sa.Column("source_version", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("anchor", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "node_kind IN ('source', 'derived')",
            name="ck_retrieval_evidence_node_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'deleted')",
            name="ck_retrieval_evidence_node_status",
        ),
        sa.CheckConstraint(
            "project_revision >= 0 AND origin_project_revision >= 0 "
            "AND origin_project_revision <= project_revision",
            name="ck_retrieval_evidence_node_revision",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["pm_project.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_ref", name="uk_retrieval_evidence_ref"),
    )
    op.create_index(
        "ix_retrieval_evidence_node_scope",
        "retrieval_evidence_node",
        ["project_id", "status", "project_revision"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_evidence_node_source",
        "retrieval_evidence_node",
        ["project_id", "source_type", "source_id"],
        unique=False,
    )
    op.create_table(
        "retrieval_evidence_root",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("evidence_node_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("root_kind", sa.String(length=32), nullable=False),
        sa.Column("source_version", sa.String(length=128), nullable=False),
        sa.Column("verification_method", sa.String(length=64), nullable=False),
        sa.Column("verification_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "root_kind IN ('project_file', 'chat_event', "
            "'business_record', 'test_execution')",
            name="ck_retrieval_evidence_root_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'revoked')",
            name="ck_retrieval_evidence_root_status",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_node_id"],
            ["retrieval_evidence_node.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["pm_project.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_node_id", name="uk_retrieval_evidence_root_node"
        ),
    )
    op.create_index(
        "ix_retrieval_evidence_root_scope",
        "retrieval_evidence_root",
        ["project_id", "status", "root_kind"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_edge_to",
        "retrieval_evidence_edge",
        ["project_id", "to_ref"],
        unique=False,
    )


def downgrade() -> None:
    # MySQL 会把 project_id 开头的复合索引作为外键支撑索引；删除整表时
    # 由数据库一并清理这些索引，提前显式删除会触发 1553。
    op.drop_table("retrieval_evidence_root")
    op.drop_table("retrieval_evidence_node")
    # 共享边表不随本 revision 删除，必须在本 revision 自有表成功删除后再回退索引。
    op.drop_index("ix_retrieval_edge_to", table_name="retrieval_evidence_edge")
