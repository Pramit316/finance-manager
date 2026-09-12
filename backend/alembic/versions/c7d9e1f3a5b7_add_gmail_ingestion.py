"""Add Gmail connections and Nabil alert processing records."""

from typing import Sequence, Union

from alembic import op

revision: str = "c7d9e1f3a5b7"
down_revision: Union[str, None] = "b6c8e0f4a2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE statement_source_enum ADD VALUE IF NOT EXISTS 'GMAIL_TRANSACTION_ALERT'")
    op.execute("""
        CREATE TABLE IF NOT EXISTS gmail_connections (
            id UUID NOT NULL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL UNIQUE,
            email VARCHAR(320) NOT NULL,
            encrypted_refresh_token TEXT NOT NULL,
            encrypted_access_token TEXT,
            token_expiry TIMESTAMP WITH TIME ZONE,
            last_successful_sync_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS gmail_messages (
            id UUID NOT NULL PRIMARY KEY,
            connection_id UUID NOT NULL REFERENCES gmail_connections(id),
            gmail_message_id VARCHAR(255) NOT NULL,
            sender VARCHAR(320) NOT NULL,
            status VARCHAR(30) NOT NULL,
            failure_reason TEXT,
            transaction_id UUID REFERENCES transactions(id),
            processed_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT uq_gmail_connection_message UNIQUE (connection_id, gmail_message_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_gmail_messages_message_id ON gmail_messages (gmail_message_id)")


def downgrade() -> None:
    op.drop_index("ix_gmail_messages_message_id", table_name="gmail_messages")
    op.drop_table("gmail_messages")
    op.drop_table("gmail_connections")