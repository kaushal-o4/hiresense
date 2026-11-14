# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/mongodb_data_layer/mongo_connection.py
#
# FILE PURPOSE:
# Creates the single MongoClient for the process and creates indexes/unique constraints declared on
# the models.
#
# WHAT THIS FILE DOES:
# 1. Opens one MongoDB client per process.
# 2. Creates indexes from model declarations (safe to run every start).
#
# HOW THIS FILE WORKS:
# database_connection.init_db() calls ensure_indexes() at startup.
#
# IMPORTANT FUNCTIONS:
#    - connect()
#        Returns one shared MongoClient (thread-safe, pooled).
#    - ensure_indexes()
#        Creates every index and unique constraint declared on the models.
#    Other helper functions: _model_list
#
# INPUT:
# MongoDB URL; model declarations.
#
# OUTPUT:
# MongoClient and indexes in the database.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/model_mapping.py
#    Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/database_session.py
#
# EXECUTION FLOW:
#    Server start
#       |
#       v
#    connect()
#       |
#       v
#    ensure_indexes()
#
# IMPORTANT DEPENDENCIES:
#    pymongo
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""The MongoClient and index creation."""
from __future__ import annotations

import threading
from datetime import timezone

from pymongo import ASCENDING, MongoClient

from .column_types import Index, UniqueConstraint
from .model_mapping import _collection_name, _registry

# --------------------------------------------------------------------------- connection

_client_lock = threading.Lock()
_client: MongoClient | None = None
_client_url: str | None = None


def connect(url: str) -> MongoClient:
    """One MongoClient per process (it is thread-safe and pools connections)."""
    global _client, _client_url
    with _client_lock:
        if _client is None or _client_url != url:
            if _client is not None:
                _client.close()
            _client = MongoClient(url, tz_aware=True, tzinfo=timezone.utc, serverSelectionTimeoutMS=5000,
                                  connectTimeoutMS=5000)
            _client_url = url
        return _client


def _model_list():
    return list(_registry.values())


def ensure_indexes(database) -> None:
    """Create the indexes and unique constraints declared on the models (safe to run on every start)."""
    for cls in _model_list():
        coll = database[_collection_name(cls)]
        specs = []
        for c in cls.__columns__.values():
            if c.primary_key:
                continue
            if c.unique:
                specs.append(((c.key,), True, None))
            elif c.index or c.fk is not None:
                specs.append(((c.key,), False, None))
        for arg in cls.__table_args__ or ():
            if isinstance(arg, UniqueConstraint):
                specs.append((tuple(cls.__columns__[n].key for n in arg.columns), True, arg.name))
            elif isinstance(arg, Index):
                specs.append((tuple(cls.__columns__[n].key for n in arg.columns), arg.unique, arg.name))
        merged: dict[tuple, tuple] = {}  # one index per key list: unique wins, an explicit name wins
        for keys, unique, name in specs:
            u0, n0 = merged.get(keys, (False, None))
            merged[keys] = (u0 or unique, n0 or name)
        for keys, (unique, name) in merged.items():
            kwargs = {}
            if name:
                kwargs["name"] = name
            if unique:
                kwargs["unique"] = True
                kwargs["partialFilterExpression"] = {
                    k: {"$type": ["number", "string", "date", "bool", "objectId"]} for k in keys}
            coll.create_index([(k, ASCENDING) for k in keys], **kwargs)
