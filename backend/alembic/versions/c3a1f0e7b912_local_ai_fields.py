"""local AI fields: interview subject, per-question difficulty/preface/meta, answer evaluation details

Only adds nullable columns, so existing rows and data are untouched.

Revision ID: c3a1f0e7b912
Revises: 08e01d05be2c
Create Date: 2026-10-10 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3a1f0e7b912'
down_revision: Union[str, Sequence[str], None] = '08e01d05be2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('interview_sessions') as b:
        b.add_column(sa.Column('subject', sa.String(length=100), nullable=True))
    with op.batch_alter_table('interview_questions') as b:
        b.add_column(sa.Column('difficulty', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('preface', sa.Text(), nullable=True))
        b.add_column(sa.Column('meta', sa.JSON(), nullable=True))
    with op.batch_alter_table('interview_answers') as b:
        b.add_column(sa.Column('details', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('interview_answers') as b:
        b.drop_column('details')
    with op.batch_alter_table('interview_questions') as b:
        b.drop_column('meta')
        b.drop_column('preface')
        b.drop_column('difficulty')
    with op.batch_alter_table('interview_sessions') as b:
        b.drop_column('subject')
