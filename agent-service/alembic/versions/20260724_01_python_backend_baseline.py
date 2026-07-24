"""建立 Python 单体后端数据库基线。

Revision ID: 20260724_01
Revises:
Create Date: 2026-07-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260724_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pm_user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="enabled",
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('enabled', 'disabled')",
            name="ck_user_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uk_user_email"),
        sa.UniqueConstraint("username", name="uk_user_username"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "pm_project",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_name", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="initializing",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('initializing', 'active', 'init_failed')",
            name="ck_project_status",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["pm_user.id"],
            name="fk_project_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "project_name",
            name="uk_project_owner_name",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "idx_project_owner_status",
        "pm_project",
        ["owner_user_id", "status"],
    )
    op.create_table(
        "pm_project_file",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "business_code",
            sa.String(length=32),
            server_default="project",
            nullable=False,
        ),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column("path_hash", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=32), nullable=True),
        sa.Column("storage_uuid", sa.String(length=16), nullable=False),
        sa.Column("storage_name", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("minio_path", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source_mtime_ms", sa.BigInteger(), nullable=False),
        sa.Column("quick_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "upload_status",
            sa.String(length=16),
            server_default="not_uploaded",
            nullable=False,
        ),
        sa.Column(
            "upload_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "parse_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("detail_ref", sa.String(length=512), nullable=True),
        sa.Column("analysis_version", sa.String(length=64), nullable=True),
        sa.Column("module", sa.String(length=128), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=True),
        sa.Column("file_type", sa.String(length=64), nullable=True),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("importance", sa.String(length=16), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.String(length=500), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "lock_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "business_code IN ('project', 'user', 'system')",
            name="ck_project_file_business",
        ),
        sa.CheckConstraint(
            "status IN ('uploading', 'active', 'updating', 'upload_failed', "
            "'verify_required', 'missing', 'deleting', 'delete_failed')",
            name="ck_project_file_status",
        ),
        sa.CheckConstraint(
            "upload_status IN ('not_uploaded', 'success', 'retrying', 'failed')",
            name="ck_project_file_upload_status",
        ),
        sa.CheckConstraint(
            "upload_attempts >= 0",
            name="ck_project_file_upload_attempts",
        ),
        sa.CheckConstraint(
            "parse_attempts >= 0",
            name="ck_project_file_parse_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["pm_project.id"],
            name="fk_project_file_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "business_code",
            "path_hash",
            name="uk_project_file_path",
        ),
        sa.UniqueConstraint(
            "object_key",
            name="uk_project_file_object_key",
        ),
        sa.UniqueConstraint(
            "project_id",
            "business_code",
            "storage_name",
            name="uk_project_file_storage_name",
        ),
        sa.UniqueConstraint(
            "project_id",
            "storage_uuid",
            name="uk_project_file_storage_uuid",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "idx_project_file_content",
        "pm_project_file",
        ["project_id", "business_code", "content_hash"],
    )
    op.create_index(
        "idx_project_file_parse",
        "pm_project_file",
        ["project_id", "parse_attempts"],
    )
    op.create_index(
        "idx_project_file_status",
        "pm_project_file",
        ["project_id", "business_code", "status"],
    )
    op.execute(
        "ALTER TABLE pm_user "
        "MODIFY updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE pm_project "
        "MODIFY updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE pm_project_file "
        "MODIFY updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP"
    )


def downgrade() -> None:
    op.drop_table("pm_project_file")
    op.drop_table("pm_project")
    op.drop_table("pm_user")
