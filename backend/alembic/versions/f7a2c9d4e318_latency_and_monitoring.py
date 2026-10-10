"""response modes, performance metrics and interview integrity monitoring

Adds two nullable columns to interview_sessions (existing rows: fast mode, not monitored) and two new tables.

Revision ID: f7a2c9d4e318
Revises: e5c8f3b1d726
Create Date: 2026-10-11 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a2c9d4e318'
down_revision: Union[str, Sequence[str], None] = 'e5c8f3b1d726'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EVENT_TYPES = ("face_absent", "multiple_faces", "attention_away", "camera_interrupted", "camera_obstructed",
               "low_light", "monitoring_interrupted", "focus_change", "permission_revoked", "monitoring_withdrawn",
               "monitoring_unavailable")


def _in(col, values):
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    with op.batch_alter_table('interview_sessions') as b:
        b.add_column(sa.Column('response_mode', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('monitoring', sa.JSON(), nullable=True))

    op.create_table(
        'perf_metrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('metric', sa.String(length=60), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('ok', sa.Boolean(), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_perf_metric_created', 'perf_metrics', ['metric', 'created_at'])

    op.create_table(
        'integrity_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('t_ms', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('confidence_sufficient', sa.Boolean(), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('candidate_explanation', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(length=20), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_in('event_type', EVENT_TYPES), name='ck_integrity_type'),
        sa.CheckConstraint(_in('severity', ("info", "low", "medium", "high")), name='ck_integrity_severity'),
        sa.CheckConstraint(_in('review_status', ("pending", "no_concern", "concern_noted", "dismissed")),
                           name='ck_integrity_review'),
    )
    op.create_index('ix_integrity_session', 'integrity_events', ['session_id', 't_ms'])


def downgrade() -> None:
    op.drop_index('ix_integrity_session', 'integrity_events')
    op.drop_table('integrity_events')
    op.drop_index('ix_perf_metric_created', 'perf_metrics')
    op.drop_table('perf_metrics')
    with op.batch_alter_table('interview_sessions') as b:
        b.drop_column('monitoring')
        b.drop_column('response_mode')
