"""MongoDB data layer with a small SQLAlchemy-style API.

The app was written against SQLAlchemy. This module keeps the same way of declaring models and writing queries
(`mapped_column`, `relationship`, `select(...).where(...)`, `db.add`, `db.commit`, ...) but stores everything in
MongoDB, so routers and services read the same as before. Only the subset of SQLAlchemy the app uses is provided.

How data is stored
  * one collection per model (`__tablename__`); the primary key is the document `_id`
  * integer ids come from a `_counters` collection, so URLs and the frontend keep using numbers
  * JSON columns are normalised the way a JSON column would be (tuples -> lists, dict keys -> strings)
  * datetimes are timezone-aware UTC (MongoDB keeps millisecond precision)
  * unique constraints and indexes are MongoDB indexes created by `ensure_indexes()`; a unique index skips
    documents where a column is null, like SQL does
  * ON DELETE CASCADE / SET NULL from `ForeignKey(..., ondelete=...)` are applied here when a row is deleted

How queries run
  Conditions on one model become a MongoDB filter (sorting, offset and limit are pushed down too). Joins, GROUP BY
  and aggregates are evaluated in Python over the matching documents, with SQL semantics (NULL never compares equal,
  COUNT(col) skips NULLs, SUM over no rows is NULL, ...). Writes are collected in the Session and sent on
  `flush()`/`commit()`; only changed fields are written (`$set`), so two requests editing different fields of the
  same document do not overwrite each other. A standalone MongoDB server has no multi-document transactions:
  a failed flush removes the documents it inserted and raises IntegrityError, which is what the app relies on.

Package layout
  coltypes     column types (String, Integer, ...), constraints, value conversion
  expressions  Column and the expression tree (comparisons, and_/or_, func, ordering)
  statements   select / update / delete and their result objects
  mapping      Base, relationship, per-object state
  connection   the MongoClient and ensure_indexes()
  query        legacy db.query() and the in-Python sort / join / dedupe helpers
  session      Session: runs statements, tracks changes, flushes to MongoDB
"""

from .coltypes import (
    JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, IntegrityError, Mapped, String, Text,
    UniqueConstraint,
)
from .connection import connect, ensure_indexes
from .expressions import (
    Binary, BoolOp, Column, Expr, Func, Label, Literal, Ordering, and_, func, mapped_column, not_, or_,
)
from .mapping import Base, InstrumentedList, relationship, set_fallback_session_factory
from .query import Query
from .session import Session
from .statements import Delete, Result, Row, ScalarResult, Select, Subquery, Update, delete, select, update

__all__ = [
    "JSON", "Base", "Binary", "BoolOp", "Boolean", "CheckConstraint", "Column", "DateTime", "Delete", "Expr", "Float",
    "ForeignKey", "Func", "Index", "InstrumentedList", "Integer", "IntegrityError", "Label", "Literal", "Mapped",
    "Ordering", "Query", "Result", "Row", "ScalarResult", "Select", "Session", "String", "Subquery", "Text",
    "UniqueConstraint", "Update", "and_", "connect", "delete", "ensure_indexes", "func", "mapped_column", "not_", "or_",
    "relationship", "select", "set_fallback_session_factory", "update",
]
