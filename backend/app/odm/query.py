"""Legacy db.query() API and the in-Python helpers for sorting, joins and dedupe."""
from __future__ import annotations

from pymongo import ASCENDING, DESCENDING

from .coltypes import _cmp_value
from .expressions import Binary, BoolOp, Column, Expr, Func, Label, _order_parts
from .statements import Delete, select
from .mapping import Base

_MISSING = object()


class Query:
    """Legacy `db.query(Model).filter(...)` style, as used by some tests and scripts."""

    def __init__(self, session, cls, stmt=None):
        self._session, self._cls = session, cls
        self._stmt = stmt if stmt is not None else select(cls)

    def _with(self, stmt):
        return Query(self._session, self._cls, stmt)

    def filter(self, *conds):
        return self._with(self._stmt.where(*conds))

    def filter_by(self, **kw):
        return self.filter(*[getattr(self._cls, k) == v for k, v in kw.items()])

    def order_by(self, *items):
        return self._with(self._stmt.order_by(*items))

    def limit(self, n):
        return self._with(self._stmt.limit(n))

    def offset(self, n):
        return self._with(self._stmt.offset(n))

    def all(self):
        return self._session.scalars(self._stmt).all()

    def first(self):
        return self._session.scalars(self._stmt.limit(1)).first()

    def one(self):
        return self._session.scalars(self._stmt).one()

    def one_or_none(self):
        return self._session.scalars(self._stmt).one_or_none()

    def count(self):
        return len(self.all())

    def get(self, pk):
        return self._session.get(self._cls, pk)

    def delete(self):
        return self._session.execute(Delete(self._cls).where(*self._stmt._where)).rowcount

    def __iter__(self):
        return iter(self.all())


def _hashable(v):
    if isinstance(v, list):
        return tuple(_hashable(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _hashable(x)) for k, x in v.items()))
    return _cmp_value(v)


def _dedupe(values):
    seen, out = set(), []
    for v in values:
        k = tuple(id(x) if isinstance(x, Base) else _hashable(x) for x in v)
        if k not in seen:
            seen.add(k)
            out.append(v)
    return out


def _slice(items, offset, limit):
    start = int(offset or 0)
    return items[start:start + int(limit)] if limit is not None else items[start:]


def _entity_key(e):
    if isinstance(e, Label):
        return e.name
    if isinstance(e, Column):
        return e.name
    if isinstance(e, type):
        return e.__name__
    if isinstance(e, Func):
        return e.name
    return None


def _ordered_models(items):
    seen = []
    for e in items:
        ms = e.models() if isinstance(e, Expr) else set()
        if isinstance(e, Column):
            ms = [e.model]
        for m in ms:
            if m not in seen:
                seen.append(m)
    return seen


def _mongo_sort(order, model):
    """MongoDB sort spec for an ORDER BY on columns of `model`, or None if it can't be pushed down."""
    spec = []
    for o in order:
        expr, desc_, nulls_first = _order_parts(o)
        if not isinstance(expr, Column) or expr.model is not model or nulls_first == desc_:
            return None  # MongoDB always sorts null lowest
        spec.append((expr.key, DESCENDING if desc_ else ASCENDING))
    if spec and spec[-1][0] != "_id":
        spec.append(("_id", ASCENDING))  # deterministic order for ties (SQLite returned rows in insert order)
    return spec


def _sort(items, order, value_of):
    items = list(items)
    for o in reversed(order):
        expr, desc_, nulls_first = _order_parts(o)
        null_rank = 0 if nulls_first != desc_ else 2  # reverse=True flips the rank too

        def key(item, expr=expr, null_rank=null_rank):
            v = _cmp_value(value_of(item, expr))
            return (null_rank, 0) if v is None else (1, v)
        try:
            items.sort(key=key, reverse=desc_)
        except TypeError:
            items.sort(key=lambda item, expr=expr, null_rank=null_rank: (
                null_rank, "") if value_of(item, expr) is None else (1, str(value_of(item, expr))), reverse=desc_)
    return items


def _infer_join(sources, target):
    for s in sources:
        for c in s.__columns__.values():
            if c.fk and c.fk.table == target.__tablename__:
                return c == target.__pk__
        for c in target.__columns__.values():
            if c.fk and c.fk.table == s.__tablename__:
                return c == s.__pk__
    raise NotImplementedError(f"Cannot work out how to join {target.__name__}")


def _join_keys(onclause, target):
    """(expression on rows so far, column of `target`, extra conditions) for an equality join."""
    conds = onclause.items if isinstance(onclause, BoolOp) and onclause.op == "and" else [onclause]
    for i, c in enumerate(conds):
        if isinstance(c, Binary) and c.op == "eq" and isinstance(c.left, Column) and isinstance(c.right, Column):
            if c.right.model is target and c.left.model is not target:
                return c.left, c.right, conds[:i] + conds[i + 1:]
            if c.left.model is target and c.right.model is not target:
                return c.right, c.left, conds[:i] + conds[i + 1:]
    raise NotImplementedError("Only equality joins are supported")
