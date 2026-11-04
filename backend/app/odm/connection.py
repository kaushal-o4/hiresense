"""The MongoClient and index creation."""
from __future__ import annotations

import threading
from datetime import timezone

from pymongo import ASCENDING, MongoClient

from .coltypes import Index, UniqueConstraint
from .mapping import _collection_name, _registry

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
