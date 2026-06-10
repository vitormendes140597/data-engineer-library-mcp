"""enable pgvector extension

Revision ID: 94467f2afd6c
Revises:
Create Date: 2026-06-03 19:39:38.893916

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "94467f2afd6c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
