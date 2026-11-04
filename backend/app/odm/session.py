"""The Session (unit of work) that runs statements against MongoDB."""
from __future__ import annotations

import itertools
import logging
from contextlib import contextmanager

from pymongo import ReturnDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError

from .coltypes import Integer, IntegrityError, _to_storage
from .expressions import Binary, BoolOp, Column, Expr, Func, Label, Literal, Ordering, _CannotPush
from .statements import Delete, Result, Row, Select, Subquery, Update, select
from .mapping import Base, InstrumentedList, _collection_name, _load_into, _state, _to_doc
from .connection import _model_list
from .query import (
    _MISSING, Query, _dedupe, _entity_key, _hashable, _infer_join, _join_keys, _mongo_sort, _ordered_models, _slice,
    _sort,
)

# --------------------------------------------------------------------------- session

class Session:
    """Unit of work over one MongoDB database (same role as sqlalchemy.orm.Session, autoflush off)."""

    def __init__(self, database):
        self.database = database
        self._identity: dict[tuple, Base] = {}
        self._new: list[Base] = []
        self._deleted: list[Base] = []
        self._after_commit: list = []

    def _is_new(self, obj) -> bool:
        return any(o is obj for o in self._new)

    # context manager
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        for obj in itertools.chain(self._identity.values(), self._new):
            st = _state(obj)
            if st.session is self:
                st.session = None
        self._identity.clear()
        self._new.clear()
        self._deleted.clear()
        self._after_commit.clear()  # closed without a commit: whatever was queued never happened

    def _coll(self, cls):
        return self.database[_collection_name(cls)]

    # ---- adding / loading
    def add(self, obj):
        st = _state(obj)
        if st.session is self and (st.persistent or self._is_new(obj)):
            self._cascade_add(obj)
            return
        if st.persistent:
            st.session = self
            self._identity[(type(obj), obj._pk)] = obj
        else:
            st.session = self
            st.deleted = False
            self._new.append(obj)
        self._cascade_add(obj)

    def _cascade_add(self, obj):
        st = _state(obj)
        related = list(st.links.values())
        for name, val in st.rel_cache.items():
            if isinstance(val, list):
                related.extend(val)
            elif val is not None:
                related.append(val)
        for r in related:
            rst = _state(r)
            if rst.session is not self and not rst.deleted:
                self.add(r)

    def add_all(self, objs):
        for o in objs:
            self.add(o)

    def _from_doc(self, cls, doc):
        key = (cls, doc["_id"])
        obj = self._identity.get(key)
        if obj is not None:
            st = _state(obj)
            if set(doc) >= set(st.snapshot) and _to_doc(obj) == st.snapshot:
                # unchanged here since it was read: take what is in the database now (another request may have
                # written it). Changes made in this session are kept until they are flushed.
                _load_into(obj, doc)
                st.snapshot = _to_doc(obj)
            return obj
        obj = cls.__new__(cls)
        st = _state(obj)
        _load_into(obj, doc)
        st.session, st.persistent, st.snapshot = self, True, _to_doc(obj)
        self._identity[key] = obj
        return obj

    def get(self, cls, pk):
        if pk is None:
            return None
        pk = _to_storage(cls.__pk__, pk)
        obj = self._identity.get((cls, pk))
        if obj is not None and _state(obj).deleted:
            return None
        doc = self._coll(cls).find_one({"_id": pk})
        if doc is None:
            return obj if obj is not None and not _state(obj).persistent else None
        return self._from_doc(cls, doc)

    def merge(self, obj):
        """Copy a (possibly unsaved) object's values onto the stored row with the same primary key, or add it."""
        cls = type(obj)
        existing = self.get(cls, obj._pk) if obj._pk is not None else None
        if existing is None:
            self.add(obj)
            return obj
        for name in cls.__columns__:
            existing.__dict__[name] = obj.__dict__.get(name)
        return existing

    def query(self, cls):
        return Query(self, cls)

    def refresh(self, obj):
        doc = self._coll(type(obj)).find_one({"_id": obj._pk})
        if doc is None:
            raise ValueError(f"{obj!r} no longer exists")
        _load_into(obj, doc)
        st = _state(obj)
        st.snapshot = _to_doc(obj)
        st.rel_cache.clear()

    def expire_all(self):
        by_cls: dict[type, list] = {}
        for (cls, pk), obj in self._identity.items():
            by_cls.setdefault(cls, []).append(pk)
        for cls, pks in by_cls.items():
            for doc in self._coll(cls).find({"_id": {"$in": pks}}):
                obj = self._identity[(cls, doc["_id"])]
                _load_into(obj, doc)
                _state(obj).snapshot = _to_doc(obj)
        for obj in self._identity.values():
            _state(obj).rel_cache.clear()

    expire = refresh

    def delete(self, obj):
        st = _state(obj)
        for i, o in enumerate(self._new):
            if o is obj:
                del self._new[i]
                st.session, st.deleted = None, True
                return
        if st.persistent and not any(o is obj for o in self._deleted):
            st.session = self
            self._deleted.append(obj)

    def expunge(self, obj):
        st = _state(obj)
        self._new = [o for o in self._new if o is not obj]
        self._identity.pop((type(obj), obj._pk), None)
        st.session = None

    # ---- writing
    def commit(self):
        self.flush()
        callbacks, self._after_commit = self._after_commit, []
        for fn in callbacks:
            try:
                fn()
            except Exception:  # noqa: BLE001 - a side effect of a commit must never undo or fail the commit
                logging.getLogger("hiresense").warning("after-commit callback failed", exc_info=True)

    def after_commit(self, fn) -> None:
        """Run `fn()` once the next commit() has written everything (used for live notifications). Dropped on
        rollback() or close() without a commit."""
        self._after_commit.append(fn)

    def flush(self):
        if not (self._new or self._deleted or self._identity):
            return
        new = list(self._new)
        # primary keys for new rows: integer ids from the counters collection, in blocks per collection
        need: dict[type, list] = {}
        for obj in new:
            cls = type(obj)
            if obj._pk is None and cls.__pk__.fk is None and cls.__pk__.type in (Integer, None):
                need.setdefault(cls, []).append(obj)
        for cls, objs in need.items():
            last = self._next_ids(cls, len(objs))
            for i, obj in enumerate(objs):
                obj.__dict__[cls.__pk__.name] = last - len(objs) + 1 + i
        # foreign keys that point at rows which only now have an id
        for _ in range(3):
            for obj in itertools.chain(new, self._identity.values()):
                st = _state(obj)
                for fk_name, parent in list(st.links.items()):
                    if parent._pk is not None:
                        obj.__dict__[fk_name] = parent._pk
                        del st.links[fk_name]
        # deletes (with ON DELETE rules)
        for obj in self._deleted:
            self._delete_ids(type(obj), [obj._pk])
        self._deleted.clear()
        # inserts
        inserted: list[tuple] = []
        try:
            groups: dict[type, list] = {}
            for obj in new:
                if obj._pk is None:
                    raise IntegrityError(f"{type(obj).__name__}: primary key is not set")
                groups.setdefault(type(obj), []).append(obj)
            for cls, objs in groups.items():
                docs = [_to_doc(o) for o in objs]
                try:
                    self._coll(cls).insert_many(docs, ordered=True)
                    inserted.extend((cls, d["_id"]) for d in docs)
                except BulkWriteError as e:
                    n = e.details.get("nInserted", 0)
                    inserted.extend((cls, d["_id"]) for d in docs[:n])
                    raise IntegrityError(str(e.details.get("writeErrors", [{}])[0].get("errmsg", e))) from None
                for o, d in zip(objs, docs):
                    st = _state(o)
                    st.persistent, st.snapshot = True, d
                    self._identity[(cls, o._pk)] = o
            self._new = [o for o in self._new if not _state(o).persistent]
            new_ids = {id(o) for o in new}
            # updates: only the fields that changed since the row was loaded or last written
            for (cls, pk), obj in list(self._identity.items()):
                st = _state(obj)
                if id(obj) in new_ids or st.deleted:
                    continue
                doc = _to_doc(obj)
                changed = {k: v for k, v in doc.items() if k != "_id" and st.snapshot.get(k, _MISSING) != v}
                if not changed:
                    continue
                for name, c in cls.__columns__.items():
                    if c.onupdate is not None and c.key not in changed:
                        obj.__dict__[name] = c.onupdate()
                        changed[c.key] = doc[c.key] = _to_storage(c, obj.__dict__[name])
                try:
                    self._coll(cls).update_one({"_id": pk}, {"$set": changed})
                except DuplicateKeyError as e:
                    raise IntegrityError(str(e)) from None
                st.snapshot = doc
        except IntegrityError:
            for cls, pk in inserted:  # undo this flush's inserts: the caller rolls back and may retry
                self._coll(cls).delete_one({"_id": pk})
                obj = self._identity.pop((cls, pk), None)
                if obj is not None:
                    _state(obj).persistent = False
            raise
        for obj in self._identity.values():
            st = _state(obj)
            for name in [n for n, v in st.rel_cache.items() if isinstance(v, InstrumentedList) or
                         type(obj).__relationships__[n].kind == "o2o"]:
                del st.rel_cache[name]

    def _next_ids(self, cls, n) -> int:
        doc = self.database["_counters"].find_one_and_update(
            {"_id": _collection_name(cls)}, {"$inc": {"seq": n}}, upsert=True, return_document=ReturnDocument.AFTER)
        return doc["seq"]

    def _delete_ids(self, cls, ids) -> int:
        ids = [i for i in ids if i is not None]
        if not ids:
            return 0
        table = cls.__tablename__
        for child in _model_list():
            for c in child.__columns__.values():
                if not c.fk or c.fk.table != table:
                    continue
                if c.fk.ondelete == "CASCADE":
                    child_ids = self._coll(child).distinct("_id", {c.key: {"$in": ids}})
                    self._delete_ids(child, child_ids)
                elif c.fk.ondelete == "SET NULL":
                    self._coll(child).update_many({c.key: {"$in": ids}}, {"$set": {c.key: None}})
                    for (k_cls, _), obj in self._identity.items():
                        if k_cls is child and obj.__dict__.get(c.name) in ids:
                            obj.__dict__[c.name] = None
                            _state(obj).snapshot[c.key] = None
        res = self._coll(cls).delete_many({"_id": {"$in": ids}})
        for pk in ids:
            obj = self._identity.pop((cls, pk), None)
            if obj is not None:
                st = _state(obj)
                st.persistent, st.deleted, st.session = False, True, None
        return res.deleted_count

    def rollback(self):
        self._after_commit.clear()
        for obj in self._new:
            st = _state(obj)
            st.session = None
        self._new.clear()
        self._deleted.clear()
        self.expire_all()

    @contextmanager
    def begin_nested(self):
        before = list(self._new)
        try:
            yield self
            self.flush()
        except Exception:
            for obj in self._new:
                if not any(obj is b for b in before):
                    _state(obj).session = None
            self._new = [o for o in self._new if any(o is b for b in before)]
            raise

    # ---- reading
    def scalars(self, stmt):
        return self.execute(stmt).scalars()

    def scalar(self, stmt):
        return self.execute(stmt).scalar()

    def execute(self, stmt, params=None):
        if isinstance(stmt, Select):
            return self._run_select(stmt)
        if isinstance(stmt, Update):
            return self._run_update(stmt)
        if isinstance(stmt, Delete):
            return self._run_delete(stmt)
        raise TypeError(f"Cannot execute {stmt!r}")

    def _push(self, model, conds):
        """Split conditions into a MongoDB filter for `model` and the rest (evaluated in Python)."""
        filters, rest = [], []
        for c in conds:
            try:
                filters.append(self._to_mongo(c, model))
            except _CannotPush:
                rest.append(c)
        filt = {"$and": filters} if len(filters) > 1 else (filters[0] if filters else {})
        return filt, rest

    def _to_mongo(self, c, model):
        if isinstance(c, Binary) and c.op in ("in", "notin") and isinstance(c.left, Column) \
                and c.left.model is model and not (isinstance(c.right, Expr) and not isinstance(c.right, Literal)):
            vals = [_to_storage(c.left, v) for v in c._right_values(self)]
            if c.op == "in":
                return {c.left.key: {"$in": [v for v in vals if v is not None]}}
            return {c.left.key: {"$nin": vals + [None]}}
        if isinstance(c, BoolOp):
            parts = [self._to_mongo(i, model) for i in c.items]
            if c.op == "and":
                return {"$and": parts} if parts else {}
            if c.op == "or":
                return {"$or": parts} if parts else {"_id": {"$exists": False}}
            return {"$nor": parts}
        return c.to_mongo(model)

    def _materialise(self, cls, docs):
        return [self._from_doc(cls, d) for d in docs]

    def _resolve_subqueries(self, e):
        """Run IN (SELECT ...) sub-selects once, before rows are filtered."""
        if isinstance(e, Binary):
            if e.op in ("in", "notin") and isinstance(e.right, (Select, Subquery)):
                return Binary(e.op, e.left, Literal(e._right_values(self)))
            return e
        if isinstance(e, BoolOp):
            return BoolOp(e.op, [self._resolve_subqueries(i) for i in e.items])
        return e

    def _run_select(self, stmt: Select) -> Result:
        if any(isinstance(w, (Binary, BoolOp)) for w in stmt._where):
            stmt = stmt._copy()
            stmt._where = [self._resolve_subqueries(w) for w in stmt._where]
        ents = stmt._entities
        src = stmt._from
        if isinstance(src, Subquery):
            inner = self._run_select(src.select)
            n = len(inner.all())
            return Result([Row(tuple(n if isinstance(e, Func) and e.name == "count" else None for e in ents),
                               [_entity_key(e) for e in ents])])
        if src is None:
            first = ents[0]
            if isinstance(first, type) and issubclass(first, Base):
                src = first
            else:
                ms = [m for m in _ordered_models(ents + stmt._where)]
                if not ms:
                    raise ValueError("select() without a model")
                src = ms[0]
        sources = [src]
        joins = []
        for target, onclause, outer in stmt._joins:
            if onclause is None:
                onclause = _infer_join(sources, target)
            sources.append(target)
            joins.append((target, onclause, outer))
        # models used in WHERE but not in FROM: join them through an equality condition (implicit join)
        where = list(stmt._where)
        referenced = set()
        for e in ents + where + [o.expr if isinstance(o, Ordering) else o for o in stmt._order] + stmt._group:
            if isinstance(e, type) and issubclass(e, Base):
                referenced.add(e)
            elif isinstance(e, Expr):
                referenced |= e.models()
        for m in [m for m in referenced if m not in sources]:
            on = next((w for w in where if isinstance(w, Binary) and w.op == "eq" and isinstance(w.left, Column)
                       and isinstance(w.right, Column) and {w.left.model, w.right.model} & {m}
                       and ({w.left.model, w.right.model} - {m}) <= set(sources)), None)
            if on is None:
                raise NotImplementedError(f"select(): {m.__name__} is used without a join")
            joins.append((m, on, False))
            sources.append(m)

        aggregate = any(isinstance(e, Expr) and e.is_aggregate for e in ents) or bool(stmt._group)
        base_filter, rest = self._push(src, where)
        coll = self._coll(src)

        # fast paths: one collection
        if not joins:
            fully_pushed = not rest
            if aggregate and not stmt._group and fully_pushed and len(ents) == 1 and isinstance(ents[0], Func) \
                    and ents[0].name == "count" and (not ents[0].args or (isinstance(ents[0].args[0], Column)
                                                                         and ents[0].args[0].primary_key)):
                return Result([Row((coll.count_documents(base_filter),), [_entity_key(ents[0])])])
            if not aggregate and fully_pushed and not stmt._distinct:
                sort = _mongo_sort(stmt._order, src)
                if sort is not None:
                    projection = None
                    if all(isinstance(e, (Column, Label)) for e in ents):
                        cols = [e.expr if isinstance(e, Label) else e for e in ents]
                        if all(isinstance(c, Column) and c.model is src for c in cols):
                            projection = {c.key: 1 for c in cols}
                    cur = coll.find(base_filter, projection)
                    if sort:
                        cur = cur.sort(sort)
                    if stmt._offset:
                        cur = cur.skip(int(stmt._offset))
                    if stmt._limit is not None:
                        cur = cur.limit(int(stmt._limit))
                    return self._project(stmt, [{src: d} for d in cur], ents)

        rows = [{src: d} for d in coll.find(base_filter)]
        for target, onclause, outer in joins:
            rows = self._join(rows, target, onclause, outer, where)
        rows = [r for r in rows if all(w.eval(r, self) is True for w in where)]

        if aggregate:
            if stmt._group:
                groups: dict = {}
                for r in rows:
                    k = tuple(_hashable(g.eval(r, self)) for g in stmt._group)
                    groups.setdefault(k, []).append(r)
                group_rows = list(groups.values())
            else:
                group_rows = [rows]
            group_rows = [g for g in group_rows if all(h.eval_group(g, self) is True for h in stmt._having)]
            out = []
            for g in group_rows:
                out.append((g, [e.eval_group(g, self) if isinstance(e, Expr) else
                                (self._from_doc(e, g[0][e]) if g and g[0].get(e) else None) for e in ents]))
            if stmt._order:
                out = _sort(out, stmt._order, lambda item, expr: expr.eval_group(item[0], self))
            values = [v for _, v in out]
            if stmt._distinct:
                values = _dedupe(values)
            values = _slice(values, stmt._offset, stmt._limit)
            keys = [_entity_key(e) for e in ents]
            return Result([Row(tuple(v), keys) for v in values])

        if stmt._order:
            rows = _sort(rows, stmt._order, lambda r, expr: expr.eval(r, self))
        if not stmt._distinct:
            rows = _slice(rows, stmt._offset, stmt._limit)
        res = self._project(stmt, rows, ents)
        if stmt._distinct:
            vals = _dedupe([tuple(r) for r in res.all()])
            keys = [_entity_key(e) for e in ents]
            return Result([Row(v, keys) for v in _slice(vals, stmt._offset, stmt._limit)])
        return res

    def _join(self, rows, target, onclause, outer, where):
        left_expr, right_col, extra = _join_keys(onclause, target)
        keys = {_hashable(left_expr.eval(r, self)) for r in rows} - {None}
        filt = {right_col.key: {"$in": list(keys)}}
        if not outer:
            pushed, _ = self._push(target, where)
            if pushed:
                filt = {"$and": [filt, pushed]}
        index: dict = {}
        for d in self._coll(target).find(filt) if keys else []:
            index.setdefault(_hashable(d.get(right_col.key)), []).append(d)
        out = []
        for r in rows:
            matches = []
            for d in index.get(_hashable(left_expr.eval(r, self)), []):
                nr = {**r, target: d}
                if all(x.eval(nr, self) is True for x in extra):
                    matches.append(nr)
            if matches:
                out.extend(matches)
            elif outer:
                out.append({**r, target: None})
        return out

    def _project(self, stmt, rows, ents):
        keys = [_entity_key(e) for e in ents]
        out = []
        for r in rows:
            vals = []
            for e in ents:
                if isinstance(e, type) and issubclass(e, Base):
                    d = r.get(e)
                    vals.append(self._from_doc(e, d) if d is not None else None)
                else:
                    vals.append(e.eval(r, self))
            out.append(Row(tuple(vals), keys))
        return Result(out)

    def _matching_ids(self, model, conds):
        filt, rest = self._push(model, conds)
        if not rest:
            return [d["_id"] for d in self._coll(model).find(filt, {"_id": 1})], filt
        ids = [o._pk for o in self.scalars(select(model).where(*conds)).all()]
        return ids, {"_id": {"$in": ids}}

    def _run_update(self, stmt: Update) -> Result:
        model = stmt.model
        sets, exprs = {}, {}
        for name, v in stmt._values.items():
            col = model.__columns__[name]
            if isinstance(v, Expr) and not isinstance(v, Literal):
                exprs[col] = v
            else:
                sets[col.key] = _to_storage(col, v.value if isinstance(v, Literal) else v)
        ids, filt = self._matching_ids(model, stmt._where)
        if exprs:
            n = 0
            for d in self._coll(model).find(filt):
                upd = dict(sets)
                for col, e in exprs.items():
                    upd[col.key] = _to_storage(col, e.eval({model: d}, self))
                n += self._coll(model).update_one({"_id": d["_id"]}, {"$set": upd}).modified_count
            count = n
        else:
            count = self._coll(model).update_many(filt, {"$set": sets}).matched_count if sets else 0
        for pk in ids:  # keep objects already loaded in this session in step with the database
            obj = self._identity.get((model, pk))
            if obj is not None:
                doc = self._coll(model).find_one({"_id": pk})
                if doc:
                    _load_into(obj, doc)
                    _state(obj).snapshot = _to_doc(obj)
        return Result(rowcount=count)

    def _run_delete(self, stmt: Delete) -> Result:
        ids, _ = self._matching_ids(stmt.model, stmt._where)
        return Result(rowcount=self._delete_ids(stmt.model, ids))
