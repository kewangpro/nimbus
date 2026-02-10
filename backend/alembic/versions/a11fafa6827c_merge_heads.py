"""merge heads

Revision ID: a11fafa6827c
Revises: 4f4d8a5c2b1a, 8908416fa8eb
Create Date: 2026-02-09 21:10:04.678645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a11fafa6827c'
down_revision: Union[str, None] = ('4f4d8a5c2b1a', '8908416fa8eb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
