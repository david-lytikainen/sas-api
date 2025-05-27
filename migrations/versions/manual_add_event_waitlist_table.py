'''Add EventWaitlist table'''
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = 'manual_waitlist'  # Needs to be unique
down_revision = '8c49fdb6c922'  # Corrected revision ID of the previous migration
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('event_waitlists',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('event_id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('waitlisted_at', sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
                    sa.ForeignKeyConstraint(['event_id'], ['events.id']),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('event_id', 'user_id', name='uq_event_user_waitlist')
                   )

def downgrade():
    op.drop_table('event_waitlists') 