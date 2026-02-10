"""Add labels and issue_labels tables

Revision ID: 4f4d8a5c2b1a
Revises: 118d72aa9234
Create Date: 2026-02-10 10:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f4d8a5c2b1a'
down_revision: Union[str, None] = '118d72aa9234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'labels',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_labels_id'), 'labels', ['id'], unique=False)
    op.create_index(op.f('ix_labels_name'), 'labels', ['name'], unique=False)

    op.create_table(
        'issue_labels',
        sa.Column('issue_id', sa.UUID(), nullable=False),
        sa.Column('label_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['label_id'], ['labels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('issue_id', 'label_id'),
    )


def downgrade() -> None:
    op.drop_table('issue_labels')
    op.drop_index(op.f('ix_labels_name'), table_name='labels')
    op.drop_index(op.f('ix_labels_id'), table_name='labels')
    op.drop_table('labels')
