"""readd pin column

Revision ID: readd_pin_column
Revises: f6e98c6ae2ac
Create Date: 2024-04-22

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "readd_pin_column"
down_revision = "f6e98c6ae2ac"
branch_labels = None
depends_on = None


def upgrade():
    # Add pin column back to events_attendees table
    op.add_column("events_attendees", sa.Column("pin", sa.String(4), nullable=True))


def downgrade():
    # Remove pin column from events_attendees table
    op.drop_column("events_attendees", "pin")
