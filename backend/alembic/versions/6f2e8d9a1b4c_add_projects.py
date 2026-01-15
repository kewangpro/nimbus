"""Add projects

Revision ID: 6f2e8d9a1b4c
Revises: 118d72aa9234
Create Date: 2026-01-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6f2e8d9a1b4c'
down_revision: Union[str, None] = 'c32ebb38d2c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create projects table
    projects_table = op.create_table('projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('owner_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=False)

    # 2. Insert Default Project
    # We use raw SQL to insert and get the ID. uuid_generate_v4() might not be available if extension not enabled, 
    # but we can generate one in python or let postgres do it if we had gen_random_uuid().
    # Let's verify pgcrypto or similar is installed? Usually safe to assume python generation for migration script if needed,
    # but op.execute is safer. 
    # Let's rely on gen_random_uuid() which is available in pgcrypto (often standard in managed pg) or just pass a literal.
    
    # Check for pgcrypto/uuid-ossp?
    # Simpler: Generate a UUID in python and inject it.
    import uuid
    general_project_id = str(uuid.uuid4())
    
    op.execute(
        f"INSERT INTO projects (id, name, description) VALUES ('{general_project_id}', 'General', 'Default project')"
    )

    # 3. Add column to issues (nullable initially)
    op.add_column('issues', sa.Column('project_id', sa.UUID(), nullable=True))

    # 4. Backfill existing issues
    op.execute(
        f"UPDATE issues SET project_id = '{general_project_id}' WHERE project_id IS NULL"
    )

    # 5. Make non-nullable
    op.alter_column('issues', 'project_id', nullable=False)

    # 6. Add constraint
    op.create_foreign_key(None, 'issues', 'projects', ['project_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'issues', type_='foreignkey')
    op.drop_column('issues', 'project_id')
    op.drop_index(op.f('ix_projects_name'), table_name='projects')
    op.drop_table('projects')
