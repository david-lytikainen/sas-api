"""make ends_at nullable

Revision ID: make_ends_at_nullable
Revises: add_pin_to_event_attendee
Create Date: 2024-04-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'make_ends_at_nullable'
down_revision = 'add_pin_to_event_attendee'
branch_labels = None
depends_on = None

def upgrade():
    # Make ends_at column nullable
    op.alter_column('events', 'ends_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

def downgrade():
    # Make ends_at column not nullable again
    op.alter_column('events', 'ends_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False) 