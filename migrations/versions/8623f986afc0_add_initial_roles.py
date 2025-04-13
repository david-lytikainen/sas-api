"""add_initial_roles

Revision ID: 8623f986afc0
Revises: 4437bd01f592
Create Date: 2025-03-24 21:51:44.184755

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '8623f986afc0'
down_revision = '4437bd01f592'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO roles (name, permission_level) VALUES 
        ('Attendee', 10),
        ('Event Organizer', 20),
        ('Admin', 30)
    """)

def downgrade():
    op.execute("""
        DELETE FROM roles WHERE name IN ('Attendee', 'Event Organizer', 'Admin')
    """)
