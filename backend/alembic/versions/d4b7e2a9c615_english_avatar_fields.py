"""english avatar fields: practice style per session, coaching meta per AI message

Only adds nullable columns, so existing rows and data are untouched.

Revision ID: d4b7e2a9c615
Revises: c3a1f0e7b912
Create Date: 2026-10-10 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4b7e2a9c615'
down_revision: Union[str, Sequence[str], None] = 'c3a1f0e7b912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('english_sessions') as b:
        b.add_column(sa.Column('style', sa.String(length=20), nullable=True))
    with op.batch_alter_table('english_messages') as b:
        b.add_column(sa.Column('meta', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('english_messages') as b:
        b.drop_column('meta')
    with op.batch_alter_table('english_sessions') as b:
        b.drop_column('style')
