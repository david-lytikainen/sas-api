"""insert roles

Revision ID: d5a696fbc3d6
Revises: 04badbee318c
Create Date: 2025-04-15 22:30:46.311546

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d5a696fbc3d6"
down_revision = "04badbee318c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO roles (name, permission_level) VALUES 
        ('Attendee', 10),
        ('Event Organizer', 20),
        ('Admin', 30)
    """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM roles WHERE name IN ('Attendee', 'Event Organizer', 'Admin')
    """
    )
