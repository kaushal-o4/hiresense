"""English companion: learning mode and conversation memory per practice session

Only adds nullable columns, so existing rows are untouched (null learning_mode = free conversation).

Revision ID: a8d3e6f1b247
Revises: f7a2c9d4e318
Create Date: 2026-10-11 00:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8d3e6f1b247'
down_revision: Union[str, Sequence[str], None] = 'f7a2c9d4e318'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('english_sessions') as b:
        b.add_column(sa.Column('learning_mode', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('memory', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('english_sessions') as b:
        b.drop_column('memory')
        b.drop_column('learning_mode')
