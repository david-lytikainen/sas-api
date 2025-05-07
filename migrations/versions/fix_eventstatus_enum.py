"""Fix EventStatus enum mapping

Revision ID: fix_eventstatus_enum
Revises: update_event_status_enum
Create Date: 2023-05-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fix_eventstatus_enum'
down_revision = 'update_event_status_enum'
branch_labels = None
depends_on = None

def upgrade():
    # Create a temporary table to hold the data
    op.execute('CREATE TABLE events_temp AS SELECT * FROM events')
    
    # Drop the original table
    op.execute('DROP TABLE events')
    
    # Get the current enum values
    op.execute('DROP TYPE eventstatus')
    
    # Create the enum type with the correct values
    op.execute("CREATE TYPE eventstatus AS ENUM ('Registration Open', 'In Progress', 'Completed', 'Cancelled', 'Paused')")
    
    # Recreate the events table with correct column types
    op.create_table('events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('starts_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('max_capacity', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('Registration Open', 'In Progress', 'Completed', 'Cancelled', 'Paused', name='eventstatus'), nullable=False),
        sa.Column('price_per_person', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('registration_deadline', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data back - converting the status values as needed
    op.execute("""
    INSERT INTO events (
        id, name, description, creator_id, starts_at, address, max_capacity, 
        status, price_per_person, registration_deadline, created_at, updated_at
    )
    SELECT 
        id, name, description, creator_id, starts_at, address, max_capacity,
        CASE 
            WHEN status = 'REGISTRATION_OPEN' THEN 'Registration Open'::eventstatus
            WHEN status = 'IN_PROGRESS' THEN 'In Progress'::eventstatus
            WHEN status = 'COMPLETED' THEN 'Completed'::eventstatus
            WHEN status = 'CANCELLED' THEN 'Cancelled'::eventstatus
            WHEN status = 'PAUSED' THEN 'Paused'::eventstatus
            ELSE 'Cancelled'::eventstatus  -- Default fallback
        END,
        price_per_person, registration_deadline, created_at, updated_at
    FROM events_temp
    """)
    
    # Drop the temporary table
    op.execute('DROP TABLE events_temp')

def downgrade():
    # This downgrade is destructive since we're converting values
    # We'll do the same thing in reverse
    op.execute('CREATE TABLE events_temp AS SELECT * FROM events')
    op.execute('DROP TABLE events')
    op.execute('DROP TYPE eventstatus')
    op.execute("CREATE TYPE eventstatus AS ENUM ('REGISTRATION_OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'PAUSED')")
    
    op.create_table('events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('starts_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('max_capacity', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('REGISTRATION_OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'PAUSED', name='eventstatus'), nullable=False),
        sa.Column('price_per_person', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('registration_deadline', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.execute("""
    INSERT INTO events (
        id, name, description, creator_id, starts_at, address, max_capacity, 
        status, price_per_person, registration_deadline, created_at, updated_at
    )
    SELECT 
        id, name, description, creator_id, starts_at, address, max_capacity,
        CASE 
            WHEN status = 'Registration Open' THEN 'REGISTRATION_OPEN'::eventstatus
            WHEN status = 'In Progress' THEN 'IN_PROGRESS'::eventstatus
            WHEN status = 'Completed' THEN 'COMPLETED'::eventstatus
            WHEN status = 'Cancelled' THEN 'CANCELLED'::eventstatus
            WHEN status = 'Paused' THEN 'PAUSED'::eventstatus
            ELSE 'CANCELLED'::eventstatus  -- Default fallback
        END,
        price_per_person, registration_deadline, created_at, updated_at
    FROM events_temp
    """)
    
    op.execute('DROP TABLE events_temp') 