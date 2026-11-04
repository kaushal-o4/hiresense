"""select / update / delete statements and their results."""
from __future__ import annotations

import copy

# --------------------------------------------------------------------------- statements

class Subquery:
    def __init__(self, select):
        self.select = select


class Select:
    def __init__(self, *entities):
        self._entities = list(entities)
        self._from = None
        self._joins: list[tuple] = []  # (model, onclause | None, outer)
        self._where: list = []
        self._order: list = []
        self._group: list = []
        self._having: list = []
        self._limit = None
        self._offset = None
        self._distinct = False

    def _copy(self):
        s = copy.copy(self)
        for attr in ("_entities", "_joins", "_where", "_order", "_group", "_having"):
            setattr(s, attr, list(getattr(self, attr)))
        return s

    def where(self, *conds):
        s = self._copy()
        s._where.extend(c for c in conds if c is not None)
        return s

    filter = where

    def join(self, target, onclause=None, isouter=False):
        s = self._copy()
        s._joins.append((target, onclause, isouter))
        return s

    def outerjoin(self, target, onclause=None):
        return self.join(target, onclause, isouter=True)

    def select_from(self, source):
        s = self._copy()
        s._from = source
        return s

    def order_by(self, *items):
        s = self._copy()
        if len(items) == 1 and items[0] is None:
            s._order = []
        else:
            s._order.extend(items)
        return s

    def group_by(self, *items):
        s = self._copy()
        s._group.extend(items)
        return s

    def having(self, *conds):
        s = self._copy()
        s._having.extend(conds)
        return s

    def limit(self, n):
        s = self._copy()
        s._limit = n
        return s

    def offset(self, n):
        s = self._copy()
        s._offset = n
        return s

    def distinct(self):
        s = self._copy()
        s._distinct = True
        return s

    def subquery(self):
        return Subquery(self)

    def scalar_subquery(self):
        return self


def select(*entities):
    return Select(*entities)


class Update:
    def __init__(self, model):
        self.model, self._where, self._values = model, [], {}

    def where(self, *conds):
        self._where.extend(conds)
        return self

    def values(self, **values):
        self._values.update(values)
        return self


class Delete:
    def __init__(self, model):
        self.model, self._where = model, []

    def where(self, *conds):
        self._where.extend(conds)
        return self


def update(model):
    return Update(model)


def delete(model):
    return Delete(model)


# --------------------------------------------------------------------------- results

class Row(tuple):
    def __new__(cls, values, keys):
        r = super().__new__(cls, values)
        r._keys = keys
        return r

    def __getattr__(self, name):
        try:
            return self[self._keys.index(name)]
        except ValueError:
            raise AttributeError(name) from None

    def _asdict(self):
        return dict(zip(self._keys, self))


class ScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)

    def first(self):
        return self._values[0] if self._values else None

    def one(self):
        if len(self._values) != 1:
            raise ValueError(f"Expected one row, got {len(self._values)}")
        return self._values[0]

    def one_or_none(self):
        if len(self._values) > 1:
            raise ValueError("Expected at most one row")
        return self.first()

    def unique(self):
        from .mapping import Base  # mapping imports this module

        seen, out = set(), []
        for v in self._values:
            k = id(v) if isinstance(v, Base) else v
            if k not in seen:
                seen.add(k)
                out.append(v)
        return ScalarResult(out)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class Result:
    def __init__(self, rows=(), rowcount=0):
        self._rows = list(rows)
        self.rowcount = rowcount

    def all(self):
        return list(self._rows)

    fetchall = all

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):
        if len(self._rows) != 1:
            raise ValueError(f"Expected one row, got {len(self._rows)}")
        return self._rows[0]

    def one_or_none(self):
        if len(self._rows) > 1:
            raise ValueError("Expected at most one row")
        return self.first()

    def scalar(self):
        return self._rows[0][0] if self._rows else None

    def scalars(self):
        return ScalarResult(r[0] for r in self._rows)

    def scalar_one(self):
        return self.scalars().one()

    def scalar_one_or_none(self):
        return self.scalars().one_or_none()

    def __iter__(self):
        return iter(self._rows)
