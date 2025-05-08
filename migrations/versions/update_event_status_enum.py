"""Update EventStatus enum to include PAUSED

Revision ID: update_event_status_enum
Revises: f6e98c6ae2ac
Create Date: 2023-06-15 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "update_event_status_enum"
down_revision = "f6e98c6ae2ac"
branch_labels = None
depends_on = None

old_options = ("Registration Open", "In Progress", "Completed", "Cancelled")
new_options = ("Registration Open", "In Progress", "Completed", "Cancelled", "Paused")

old_type = sa.Enum(*old_options, name="eventstatus")
new_type = sa.Enum(*new_options, name="eventstatus")


def upgrade():
    # Create a temporary table to store current values
    op.execute("ALTER TYPE eventstatus RENAME TO eventstatus_old")

    # Create new enum type with the added value
    new_type.create(op.get_bind())

    # Update the columns to use the new type
    op.execute(
        "ALTER TABLE events ALTER COLUMN status TYPE eventstatus USING status::text::eventstatus"
    )

    # Drop the old type
    op.execute("DROP TYPE eventstatus_old")


def downgrade():
    # This is risky as we might have records with the 'Paused' value
    # Create a temporary table to store current values - convert 'Paused' to 'Cancelled'
    op.execute("ALTER TYPE eventstatus RENAME TO eventstatus_old")

    # Create old enum type without the 'Paused' value
    old_type.create(op.get_bind())

    # Update the columns to use the old type - convert 'Paused' to 'Cancelled'
    op.execute(
        "ALTER TABLE events ALTER COLUMN status TYPE eventstatus USING CASE WHEN status::text = 'Paused' THEN 'Cancelled'::eventstatus ELSE status::text::eventstatus END"
    )

    # Drop the old type
    op.execute("DROP TYPE eventstatus_old")
