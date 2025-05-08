"""add pin to event attendee

Revision ID: add_pin_to_event_attendee
Revises: 524597c5a834
Create Date: 2024-04-22

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_pin_to_event_attendee"
down_revision = "524597c5a834"
branch_labels = None
depends_on = None


def upgrade():
    # Add pin column to events_attendees table
    op.add_column("events_attendees", sa.Column("pin", sa.String(4), nullable=True))


def downgrade():
    # Remove pin column from events_attendees table
    op.drop_column("events_attendees", "pin")
