"""Add manual transactions and monthly budgets."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a4b7c9d2e1f3"
down_revision: Union[str, None] = "d10eda928ccc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE statement_source_enum ADD VALUE IF NOT EXISTS 'MANUAL'")
    op.execute("ALTER TYPE statement_source_enum ADD VALUE IF NOT EXISTS 'STANDARD_CHARTERED'")
    op.alter_column("transactions", "statement_import_id", nullable=True)
    op.add_column("transactions", sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("transactions", sa.Column("payment_method", sa.String(length=30), nullable=True))

    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("expected_income", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("planned_saving", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "month", name="uq_monthly_budget_year_month"),
    )
    allocation_type = sa.Enum("CONSUMPTION", "INVESTMENT", name="allocation_type_enum")
    op.create_table(
        "budget_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("monthly_budget_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("planned_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("allocation_type", allocation_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monthly_budget_id"], ["monthly_budgets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("monthly_budget_id", "category", name="uq_budget_allocation_category"),
    )


def downgrade() -> None:
    op.drop_table("budget_allocations")
    op.get_bind().execute(sa.text("DROP TYPE IF EXISTS allocation_type_enum"))
    op.drop_table("monthly_budgets")
    op.drop_column("transactions", "payment_method")
    op.drop_column("transactions", "is_manual")
    op.alter_column("transactions", "statement_import_id", nullable=False)