"""add sync job claim index

Revision ID: fdec44f4f4c9
Revises: 92f6aa9e8ed7
Create Date: 2026-09-09 14:49:06.977064

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'fdec44f4f4c9'
down_revision = '92f6aa9e8ed7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sync_jobs', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_sync_jobs_status_next_attempt_at'),
            ['status', 'next_attempt_at'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('sync_jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sync_jobs_status_next_attempt_at'))
