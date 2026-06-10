"""Add error traceback to processing failures.

Revision ID: 2b7c7d0e5d3a
Revises: b5e0fa612fe0
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2b7c7d0e5d3a"
down_revision = "b5e0fa612fe0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processing_failures",
        sa.Column("error_traceback", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE processing_failures SET error_traceback = error_message "
        "WHERE error_traceback IS NULL"
    )
    op.alter_column("processing_failures", "error_traceback", nullable=False)


def downgrade() -> None:
    op.drop_column("processing_failures", "error_traceback")
