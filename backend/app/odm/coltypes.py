"""Column types, model-declaration helpers and value conversion."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from .expressions import Column

T = TypeVar("T")


class IntegrityError(Exception):
    """A unique constraint was violated (raised in place of sqlalchemy.exc.IntegrityError)."""


class Mapped(Generic[T]):
    """Annotation marker only (`id: Mapped[int] = mapped_column(...)`)."""


# --------------------------------------------------------------------------- column types

class _Type:
    def __init__(self, *args, **kwargs):
        pass


class String(_Type):
    pass


class Text(_Type):
    pass


class Integer(_Type):
    pass


class Float(_Type):
    pass


class Boolean(_Type):
    pass


class DateTime(_Type):
    pass


class JSON(_Type):
    pass


class ForeignKey:
    def __init__(self, target: str, ondelete: str | None = None):
        self.table, self.column = target.split(".")
        self.ondelete = (ondelete or "").upper() or None


class UniqueConstraint:
    def __init__(self, *columns: str, name: str | None = None):
        self.columns, self.name = columns, name


class Index:
    def __init__(self, name: str, *columns: str, unique: bool = False):
        self.name, self.columns, self.unique = name, columns, unique


def CheckConstraint(*args, **kwargs):  # noqa: N802 - SQLAlchemy name; validation happens in the API schemas
    return None


# --------------------------------------------------------------------------- values

def _utc(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


def _json_default(o):
    if hasattr(o, "tolist"):  # numpy arrays and scalars
        return o.tolist()
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, (set, frozenset)):
        return list(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _to_storage(col: "Column", v):
    if v is None:
        return None
    t = col.type
    if t is JSON:
        return json.loads(json.dumps(v, default=_json_default))
    if t is Integer:
        return v if isinstance(v, bool) else int(v)
    if t is Float:
        return float(v)
    if t is Boolean:
        return bool(v)
    if t is DateTime:
        if isinstance(v, datetime):
            return _utc(v)
        if isinstance(v, date):
            return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
        return v
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        return v.item()
    return v


def _cmp_value(v):
    """Normalise a value for comparisons evaluated in Python."""
    if isinstance(v, datetime):
        v = _utc(v)
        return v.replace(microsecond=v.microsecond // 1000 * 1000)  # MongoDB keeps milliseconds
    return v
