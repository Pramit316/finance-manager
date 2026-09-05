"""Add Standard Chartered as a statement source."""

from typing import Sequence, Union
from alembic import op

revision: str = "b6c8e0f4a2d1"
down_revision: Union[str, None] = "a4b7c9d2e1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE statement_source_enum ADD VALUE IF NOT EXISTS 'STANDARD_CHARTERED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely in place.
    pass