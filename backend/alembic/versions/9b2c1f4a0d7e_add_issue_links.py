"""Add issue links table

Revision ID: 9b2c1f4a0d7e
Revises: 6e4d6f9c3d2a
Create Date: 2026-02-10 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b2c1f4a0d7e'
down_revision: Union[str, None] = '6e4d6f9c3d2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'issue_links',
        sa.Column('issue_id', sa.UUID(), nullable=False),
        sa.Column('depends_on_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['depends_on_id'], ['issues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('issue_id', 'depends_on_id'),
    )


def downgrade() -> None:
    op.drop_table('issue_links')
