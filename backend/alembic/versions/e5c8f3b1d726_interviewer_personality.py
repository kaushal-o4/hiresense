"""interviewer personality per interview session

Only adds a nullable column, so existing rows and data are untouched (null = Aria).

Revision ID: e5c8f3b1d726
Revises: d4b7e2a9c615
Create Date: 2026-10-10 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5c8f3b1d726'
down_revision: Union[str, Sequence[str], None] = 'd4b7e2a9c615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('interview_sessions') as b:
        b.add_column(sa.Column('interviewer', sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('interview_sessions') as b:
        b.drop_column('interviewer')
