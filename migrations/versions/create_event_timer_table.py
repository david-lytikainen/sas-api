"""create event timer table

Revision ID: 8c49fdb6c922
Revises: 
Create Date: 2023-04-26 10:47:23.233981

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c49fdb6c922'
down_revision = None  # Update this to the most recent migration ID
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('event_timers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('current_round', sa.Integer(), nullable=False, server_default='1'),
    sa.Column('round_duration', sa.Integer(), nullable=False, server_default='180'),
    sa.Column('round_start_time', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('is_paused', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('pause_time_remaining', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('event_timers') 