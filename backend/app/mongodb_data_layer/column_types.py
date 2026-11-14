# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/mongodb_data_layer/column_types.py
#
# FILE PURPOSE:
# Defines field types (String, Text, Integer, Float, Boolean, DateTime, JSON), ForeignKey, unique
# constraints and indexes used when declaring models, plus value conversion for storage.
#
# WHAT THIS FILE DOES:
# 1. Provides column type classes used in database_models.py.
# 2. Provides ForeignKey, UniqueConstraint and Index declarations (turned into MongoDB indexes).
# 3. Converts Python values (dates, tuples, JSON) into what MongoDB stores.
# 4. Defines IntegrityError for unique-constraint violations.
#
# HOW THIS FILE WORKS:
# Each type knows how to convert a value before saving (_to_storage) and how to compare values when a
# filter has to be evaluated in Python (_cmp_value).
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: CheckConstraint, _utc, _json_default, _to_storage, _cmp_value
#
# IMPORTANT CLASSES:
#    - IntegrityError
#        A unique constraint was violated (raised in place of sqlalchemy.exc.IntegrityError).
#    - Mapped
#        Annotation marker only (`id: Mapped[int] = mapped_column(...)`).
#    - _Type
#    - String
#    - Text
#    - Integer
#    - Float
#    - Boolean
#    - DateTime
#    - JSON
#    - ForeignKey
#    - UniqueConstraint
#    - Index
#
# INPUT:
# Field declarations and Python values.
#
# OUTPUT:
# Storable values and index definitions.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/mongodb_data_layer/query_expressions.py
#    Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/database_session.py,
#    app/mongodb_data_layer/legacy_query_api.py, app/mongodb_data_layer/model_mapping.py,
#    app/mongodb_data_layer/mongo_connection.py, app/mongodb_data_layer/query_expressions.py
#
# EXECUTION FLOW:
#    Model declares mapped_column(String(...))
#       |
#       v
#    Value assigned
#       |
#       v
#    Converted for MongoDB on save
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Column types, model-declaration helpers and value conversion."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from .query_expressions import Column

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
