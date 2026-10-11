"""integrity detectors: paste, fullscreen / second display, phone or notes in view

Only widens the allowed event types of integrity_events (no data changes).

Revision ID: b9e4d2c7a531
Revises: a8d3e6f1b247
Create Date: 2026-10-12 10:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b9e4d2c7a531'
down_revision: Union[str, Sequence[str], None] = 'a8d3e6f1b247'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPES = ("face_absent", "multiple_faces", "attention_away", "camera_interrupted", "camera_obstructed",
             "low_light", "monitoring_interrupted", "focus_change", "permission_revoked", "monitoring_withdrawn",
             "monitoring_unavailable")
NEW_TYPES = OLD_TYPES + ("paste_detected", "paste_long", "fullscreen_exit", "second_display", "phone_in_view",
                         "notes_in_view")


def _in(col, values):
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    with op.batch_alter_table('integrity_events') as b:
        b.drop_constraint('ck_integrity_type', type_='check')
        b.create_check_constraint('ck_integrity_type', _in('event_type', NEW_TYPES))


def downgrade() -> None:
    op.execute(f"DELETE FROM integrity_events WHERE event_type IN ({', '.join(repr(v) for v in NEW_TYPES[len(OLD_TYPES):])})")
    with op.batch_alter_table('integrity_events') as b:
        b.drop_constraint('ck_integrity_type', type_='check')
        b.create_check_constraint('ck_integrity_type', _in('event_type', OLD_TYPES))
