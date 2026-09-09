"""为长运行增加互斥作用域和可恢复租约。

Revision ID: 20260909_01
Revises: 20260908_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_01"
down_revision = "20260908_01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agent_run") as batch:
        batch.add_column(sa.Column("active_scope_key", sa.String(160), nullable=True))
        batch.add_column(sa.Column("lease_until", sa.DateTime(), nullable=True))
        batch.create_unique_constraint("uk_run_active_scope", ["active_scope_key"])


def downgrade():
    with op.batch_alter_table("agent_run") as batch:
        batch.drop_constraint("uk_run_active_scope", type_="unique")
        batch.drop_column("lease_until")
        batch.drop_column("active_scope_key")
