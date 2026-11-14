# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/mongodb_data_layer/__init__.py
#
# FILE PURPOSE:
# The front door of the project's own MongoDB data layer. It re-exports a small SQLAlchemy-style API
# (select, update, delete, Session, Base, mapped_column, relationship, func, ...) implemented on top
# of pymongo.
#
# MAIN RESPONSIBILITY:
# Lets the rest of the code write SQLAlchemy-like queries while data is stored in MongoDB.
#
# WHAT THIS FILE DOES:
# 1. Imports and re-exports the public names of the sibling modules.
# 2. Documents how data is stored: one collection per model, integer ids from a counters
#    collection.
#
# HOW THIS FILE WORKS:
# The application was first written with SQLAlchemy (SQL). When it moved to MongoDB, this layer was
# written so routers and services could keep the same query style:
# `db.scalars(select(User).where(User.email == x))`.
#
# INPUT:
# Imports from the modules in this folder.
#
# OUTPUT:
# Names used across the backend: `from ..mongodb_data_layer import select, Session`.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/database_session.py,
#    app/mongodb_data_layer/legacy_query_api.py, app/mongodb_data_layer/model_mapping.py,
#    app/mongodb_data_layer/mongo_connection.py, app/mongodb_data_layer/query_expressions.py,
#    app/mongodb_data_layer/query_statements.py
#    Used by: app/authentication_dependencies.py, app/database_connection.py,
#    app/database_models.py, app/main.py, app/reset_admin_password.py,
#    app/routers/admin/admin_analytics_routes.py, app/routers/admin/admin_content_routes.py,
#    app/routers/admin/admin_operations_routes.py,
#    app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
#    app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
#    app/routers/interview_routes.py, app/routers/jobs/job_shared_helpers.py,
#    app/routers/jobs/recruiter_job_routes.py, app/routers/jobs/recruiter_screening_routes.py,
#    app/routers/jobs/student_job_routes.py, app/routers/live_voice_interview_routes.py,
#    app/routers/mentor_portal_routes.py, app/routers/profile_and_notification_routes.py,
#    app/routers/skill_assessment_routes.py, app/routers/student_portal_routes.py,
#    app/routers/voice_speech_routes.py, app/seed_initial_data.py, app/seed_sample_jobs.py,
#    app/services/ai_models/ai_structured_call_base.py,
#    app/services/english/ai_english_conversation.py,
#    app/services/english/english_mistake_profile.py,
#    app/services/english/english_vocabulary_trainer.py,
#    app/services/interview/ai_interview_service.py, app/services/monitoring/performance_timing.py,
#    app/services/platform_support/audit_and_notification_helpers.py,
#    app/services/platform_support/student_record_access.py,
#    app/services/resume_and_jobs/ai_career_and_assessment_tasks.py,
#    app/services/resume_and_jobs/ai_resume_analyzer.py,
#    app/services/resume_and_jobs/semantic_job_matcher.py,
#    app/services/student_progress/rewards_and_badges.py,
#    app/services/student_progress/student_performance_insights.py
#    Tested by: tests/test_account_security.py, tests/test_deploy.py, tests/test_english_vocab.py,
#    tests/test_odm.py, tests_e2e/account_browser.py, tests_perf/bench_prompts.py
#
# EXECUTION FLOW:
#    Router imports select/Session from here
#       |
#       v
#    Builds a query
#       |
#       v
#    Session runs it against MongoDB
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

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

from .column_types import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    IntegrityError,
    Mapped,
    String,
    Text,
    UniqueConstraint,
)
from .mongo_connection import connect, ensure_indexes
from .query_expressions import (
    Binary,
    BoolOp,
    Column,
    Expr,
    Func,
    Label,
    Literal,
    Ordering,
    and_,
    func,
    mapped_column,
    not_,
    or_,
)
from .model_mapping import Base, InstrumentedList, relationship, set_fallback_session_factory
from .legacy_query_api import Query
from .database_session import Session
from .query_statements import Delete, Result, Row, ScalarResult, Select, Subquery, Update, delete, select, update

__all__ = [
    "JSON", "Base", "Binary", "BoolOp", "Boolean", "CheckConstraint", "Column", "DateTime", "Delete", "Expr", "Float",
    "ForeignKey", "Func", "Index", "InstrumentedList", "Integer", "IntegrityError", "Label", "Literal", "Mapped",
    "Ordering", "Query", "Result", "Row", "ScalarResult", "Select", "Session", "String", "Subquery", "Text",
    "UniqueConstraint", "Update", "and_", "connect", "delete", "ensure_indexes", "func", "mapped_column", "not_", "or_",
    "relationship", "select", "set_fallback_session_factory", "update",
]
