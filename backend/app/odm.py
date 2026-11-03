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
"""
from __future__ import annotations

import copy
import itertools
import json
import re
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Generic, TypeVar

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError

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


# --------------------------------------------------------------------------- expressions

class _CannotPush(Exception):
    pass


class Expr:
    is_aggregate = False

    def models(self) -> set:
        return set()

    def eval(self, row, sess):
        raise NotImplementedError

    def eval_group(self, rows, sess):
        return self.eval(rows[0], sess) if rows else None

    def to_mongo(self, model):
        raise _CannotPush

    # comparisons
    def __eq__(self, other):  # type: ignore[override]
        return Binary("is" if other is None else "eq", self, _lit(other))

    def __ne__(self, other):  # type: ignore[override]
        return Binary("isnot" if other is None else "ne", self, _lit(other))

    def __lt__(self, other):
        return Binary("lt", self, _lit(other))

    def __le__(self, other):
        return Binary("le", self, _lit(other))

    def __gt__(self, other):
        return Binary("gt", self, _lit(other))

    def __ge__(self, other):
        return Binary("ge", self, _lit(other))

    def __add__(self, other):
        return Binary("add", self, _lit(other))

    def __sub__(self, other):
        return Binary("sub", self, _lit(other))

    def __mul__(self, other):
        return Binary("mul", self, _lit(other))

    def __truediv__(self, other):
        return Binary("div", self, _lit(other))

    __hash__ = object.__hash__

    def in_(self, values):
        return Binary("in", self, values if isinstance(values, (Select, Subquery)) else Literal(list(values)))

    def not_in(self, values):
        return Binary("notin", self, values if isinstance(values, (Select, Subquery)) else Literal(list(values)))

    notin_ = not_in

    def is_(self, value):
        return Binary("is", self, _lit(value))

    def is_not(self, value):
        return Binary("isnot", self, _lit(value))

    isnot = is_not

    def ilike(self, pattern):
        return Binary("regex", self, Literal(_like_regex(pattern, ignore_case=True)))

    def like(self, pattern):
        return Binary("regex", self, Literal(_like_regex(pattern, ignore_case=False)))

    def startswith(self, prefix):
        return Binary("regex", self, Literal(re.compile("^" + re.escape(prefix), re.S)))

    def endswith(self, suffix):
        return Binary("regex", self, Literal(re.compile(re.escape(suffix) + "$", re.S)))

    def contains(self, part):
        return Binary("regex", self, Literal(re.compile(re.escape(part), re.S)))

    def desc(self):
        return Ordering(self, True)

    def asc(self):
        return Ordering(self, False)

    def label(self, name):
        return Label(self, name)

    def __bool__(self):
        raise TypeError("A query expression has no truth value; use and_()/or_() to combine conditions")


def _like_regex(pattern: str, ignore_case: bool):
    out = []
    for ch in pattern:
        out.append(".*" if ch == "%" else "." if ch == "_" else re.escape(ch))
    return re.compile("^" + "".join(out) + "$", (re.I if ignore_case else 0) | re.S)


def _lit(v):
    return v if isinstance(v, Expr) else Literal(v)


class Literal(Expr):
    def __init__(self, value):
        self.value = value

    def eval(self, row, sess):
        return self.value

    def eval_group(self, rows, sess):
        return self.value


class Column(Expr):
    """A model column. On the class it is a query expression (`User.email == x`), on an instance it is the value."""

    def __init__(self, *args, primary_key=False, default=None, nullable=True, unique=False, index=False,
                 server_default=None, onupdate=None):
        self.type = None
        self.fk: ForeignKey | None = None
        for a in args:
            if isinstance(a, ForeignKey):
                self.fk = a
            elif isinstance(a, type) and issubclass(a, _Type):
                self.type = a
            elif isinstance(a, _Type):
                self.type = type(a)
        if self.fk and self.type is None:
            self.type = Integer
        self.primary_key = primary_key
        self.default = default
        self.nullable = nullable
        self.unique = unique
        self.index = index
        self.onupdate = onupdate
        self.model = None
        self.name = None

    def __set_name__(self, owner, name):
        self.model, self.name = owner, name

    def bound_copy(self, model):
        c = copy.copy(self)
        c.model = model
        return c

    @property
    def key(self) -> str:
        return "_id" if self.primary_key else self.name

    def make_default(self):
        d = self.default
        if callable(d):
            return d()
        return copy.deepcopy(d)

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name)

    def __set__(self, obj, value):
        obj.__dict__[self.name] = value

    def models(self):
        return {self.model}

    def eval(self, row, sess):
        doc = row.get(self.model)
        return None if doc is None else doc.get(self.key)

    def to_mongo(self, model):
        raise _CannotPush

    def __repr__(self):
        return f"{getattr(self.model, '__name__', '?')}.{self.name}"


mapped_column = Column


class Binary(Expr):
    def __init__(self, op, left, right):
        self.op, self.left, self.right = op, left, right

    @property
    def is_aggregate(self):
        return self.left.is_aggregate or (isinstance(self.right, Expr) and self.right.is_aggregate)

    def models(self):
        m = self.left.models()
        if isinstance(self.right, Expr):
            m |= self.right.models()
        return m

    def _right_values(self, sess):
        r = self.right
        if isinstance(r, (Select, Subquery)):
            sel = r.select if isinstance(r, Subquery) else r
            return [row[0] for row in sess.execute(sel).all()]
        return r.value

    def to_mongo(self, model):
        if not isinstance(self.left, Column) or self.left.model is not model:
            raise _CannotPush
        if isinstance(self.right, Column):
            raise _CannotPush
        k, op = self.left.key, self.op
        if op in ("in", "notin"):
            raise _CannotPush  # handled by Session._to_mongo (sub-selects need the session)
        if not isinstance(self.right, Literal):
            raise _CannotPush
        v = _to_storage(self.left, self.right.value) if op != "regex" else self.right.value
        if op in ("eq", "is"):
            return {k: v}
        if op in ("ne", "isnot"):
            return {k: {"$ne": None}} if v is None else ({k: {"$ne": v}} if op == "isnot" else {k: {"$nin": [v, None]}})
        if op in ("lt", "le", "gt", "ge"):
            if v is None:
                return {"_id": {"$exists": False}}  # comparing with NULL is never true
            return {k: {"$" + {"lt": "lt", "le": "lte", "gt": "gt", "ge": "gte"}[op]: v}}
        if op == "regex":
            return {k: {"$regex": v.pattern, "$options": ("i" if v.flags & re.I else "") + "s"}}
        raise _CannotPush

    def eval(self, row, sess):
        op = self.op
        a = _cmp_value(self.left.eval(row, sess))
        if op in ("in", "notin"):
            if a is None:
                return None
            vals = [_cmp_value(x) for x in self._right_values(sess)]
            return (a in vals) if op == "in" else (a not in vals)
        b = _cmp_value(self.right.eval(row, sess))
        return _apply(op, a, b)

    def eval_group(self, rows, sess):
        if not self.is_aggregate:
            return super().eval_group(rows, sess)
        a = _cmp_value(self.left.eval_group(rows, sess))
        b = _cmp_value(self.right.eval_group(rows, sess)) if isinstance(self.right, Expr) else self.right
        return _apply(self.op, a, b)


def _apply(op, a, b):
    if op == "is":
        return a == b if b is not None else a is None
    if op == "isnot":
        return a != b if b is not None else a is not None
    if a is None or b is None:
        return None
    try:
        if op == "eq":
            return a == b
        if op == "ne":
            return a != b
        if op == "lt":
            return a < b
        if op == "le":
            return a <= b
        if op == "gt":
            return a > b
        if op == "ge":
            return a >= b
    except TypeError:
        return None
    if op == "regex":
        return bool(b.search(a)) if isinstance(a, str) else None
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "div":
        return a / b if b else None
    raise ValueError(op)


class BoolOp(Expr):
    def __init__(self, op, items):
        self.op, self.items = op, [i for i in items if i is not None]

    def models(self):
        m = set()
        for i in self.items:
            m |= i.models()
        return m

    def eval(self, row, sess):
        vals = [i.eval(row, sess) for i in self.items]
        if self.op == "not":
            return None if vals[0] is None else not vals[0]
        if self.op == "and":
            if any(v is False for v in vals):
                return False
            return None if any(v is None for v in vals) else True
        if any(v is True for v in vals):
            return True
        return None if any(v is None for v in vals) else False

    def to_mongo(self, model):
        parts = [i.to_mongo(model) for i in self.items]
        if self.op == "and":
            return {"$and": parts} if parts else {}
        if self.op == "or":
            return {"$or": parts} if parts else {"_id": {"$exists": False}}
        return {"$nor": parts}


def and_(*items):
    return BoolOp("and", items)


def or_(*items):
    return BoolOp("or", items)


def not_(item):
    return BoolOp("not", [item])


class Func(Expr):
    AGGREGATES = {"count", "sum", "avg", "max", "min"}

    def __init__(self, name, args):
        self.name, self.args = name, [_lit(a) for a in args]

    @property
    def is_aggregate(self):
        return self.name in self.AGGREGATES or any(a.is_aggregate for a in self.args)

    def models(self):
        m = set()
        for a in self.args:
            m |= a.models()
        return m

    def eval(self, row, sess):
        if self.name in self.AGGREGATES:
            return self.eval_group([row], sess)
        vals = [a.eval(row, sess) for a in self.args]
        return self._scalar(vals)

    def _scalar(self, vals):
        if self.name == "coalesce":
            return next((v for v in vals if v is not None), None)
        if self.name == "lower":
            return vals[0].lower() if isinstance(vals[0], str) else vals[0]
        if self.name == "upper":
            return vals[0].upper() if isinstance(vals[0], str) else vals[0]
        if self.name == "length":
            return len(vals[0]) if vals[0] is not None else None
        raise NotImplementedError(f"func.{self.name}")

    def eval_group(self, rows, sess):
        n = self.name
        if n == "count":
            if not self.args:
                return len(rows)
            return sum(1 for r in rows if self.args[0].eval(r, sess) is not None)
        if n in ("sum", "avg", "max", "min"):
            vals = [v for v in (self.args[0].eval(r, sess) for r in rows) if v is not None]
            if not vals:
                return None
            if n == "sum":
                return sum(vals)
            if n == "avg":
                return sum(vals) / len(vals)
            return max(vals) if n == "max" else min(vals)
        return self._scalar([a.eval_group(rows, sess) for a in self.args])


class _FuncFactory:
    def __getattr__(self, name):
        return lambda *args: Func(name, args)


func = _FuncFactory()


class Label(Expr):
    def __init__(self, expr, name):
        self.expr, self.name = expr, name

    @property
    def is_aggregate(self):
        return self.expr.is_aggregate

    def models(self):
        return self.expr.models()

    def eval(self, row, sess):
        return self.expr.eval(row, sess)

    def eval_group(self, rows, sess):
        return self.expr.eval_group(rows, sess)


class Ordering:
    def __init__(self, expr, descending, nulls=None):
        self.expr, self.descending, self.nulls = expr, descending, nulls

    def nulls_last(self):
        return Ordering(self.expr, self.descending, "last")

    def nulls_first(self):
        return Ordering(self.expr, self.descending, "first")

    nullslast, nullsfirst = nulls_last, nulls_first


def _order_parts(o):
    """(expression, descending, nulls first?) for an ORDER BY item. Default as in SQLite: NULLs sort lowest."""
    if isinstance(o, Ordering):
        nulls_first = (not o.descending) if o.nulls is None else o.nulls == "first"
        return o.expr, o.descending, nulls_first
    return o, False, True


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


# --------------------------------------------------------------------------- models

_registry: dict[str, type] = {}  # table name -> model
_by_name: dict[str, type] = {}  # class name -> model


class _State:
    __slots__ = ("session", "persistent", "snapshot", "rel_cache", "links", "deleted")

    def __init__(self):
        self.session = None
        self.persistent = False
        self.snapshot = None
        self.rel_cache = {}
        self.links = {}  # fk column name -> parent object whose primary key goes into it at flush
        self.deleted = False


def _state(obj) -> _State:
    st = obj.__dict__.get("_odm_state")
    if st is None:
        st = obj.__dict__["_odm_state"] = _State()
    return st


class Base:
    __tablename__: str
    __table_args__: tuple = ()
    __columns__: dict
    __relationships__: dict
    __pk__: Column

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "__tablename__" not in cls.__dict__:
            return
        cols, rels = {}, {}
        for klass in reversed(cls.__mro__):
            for name, val in list(vars(klass).items()):
                if isinstance(val, Column):
                    if val.model is not cls:
                        val = val.bound_copy(cls)
                        setattr(cls, name, val)
                    cols[name] = val
                elif isinstance(val, relationship):
                    rels[name] = val
        cls.__columns__ = cols
        cls.__relationships__ = rels
        pks = [c for c in cols.values() if c.primary_key]
        if len(pks) != 1:
            raise TypeError(f"{cls.__name__} needs exactly one primary key column")
        cls.__pk__ = pks[0]
        _registry[cls.__tablename__] = cls
        _by_name[cls.__name__] = cls

    def __init__(self, **kwargs):
        st = _state(self)
        for name, col in type(self).__columns__.items():
            if name not in kwargs:
                self.__dict__[name] = col.make_default() if col.default is not None else None
        for k, v in kwargs.items():
            if k not in type(self).__columns__ and k not in type(self).__relationships__:
                raise TypeError(f"{k!r} is an invalid keyword argument for {type(self).__name__}")
            setattr(self, k, v)
        st.persistent = False

    def __repr__(self):
        return f"<{type(self).__name__} {self._pk!r}>"

    @property
    def _pk(self):
        return self.__dict__.get(type(self).__pk__.name)


def _collection_name(cls) -> str:
    return cls.__tablename__


def _to_doc(obj) -> dict:
    cls = type(obj)
    return {c.key: _to_storage(c, obj.__dict__.get(name)) for name, c in cls.__columns__.items()}


def _load_into(obj, doc):
    cls = type(obj)
    for name, c in cls.__columns__.items():
        if c.key in doc:
            obj.__dict__[name] = doc[c.key]
        elif name not in obj.__dict__:
            obj.__dict__[name] = c.make_default() if c.default is not None else None


class relationship:  # noqa: N801 - SQLAlchemy name
    """Related objects, loaded on first access.

    Many-to-one (`answer.question`) follows a foreign key on this model. One-to-many (`session.questions`) and
    one-to-one (`user.student_profile`) find rows of the other model whose foreign key points here. Collections
    support append/remove/clear; with cascade "delete-orphan" a removed child is deleted.
    """

    def __init__(self, *args, back_populates=None, uselist=None, cascade="", order_by=None, foreign_keys=None,
                 **kwargs):
        self.back_populates = back_populates
        self.uselist_arg = uselist
        self.delete_orphan = "delete-orphan" in (cascade or "")
        self.order_by_arg = order_by
        self.foreign_keys = foreign_keys
        self.owner = None
        self.name = None
        self._resolved = False

    def __set_name__(self, owner, name):
        self.owner, self.name = owner, name

    def _resolve(self):
        if self._resolved:
            return
        text = _annotation_text(self.owner, self.name)
        names = [n for n in re.findall(r"[A-Za-z_]\w*", text) if n in _by_name]
        if not names:
            raise TypeError(f"Cannot find the target model of {self.owner.__name__}.{self.name} ({text!r})")
        target = _by_name[names[-1]]
        is_list = "list[" in text or "List[" in text
        if self.uselist_arg is not None:
            is_list = self.uselist_arg
        self.target = target
        self.is_list = is_list
        if self.foreign_keys:
            self.kind, self.fk = "m2o", self.owner.__columns__[self.foreign_keys[0].name]
        else:
            local = [c for c in self.owner.__columns__.values() if c.fk and c.fk.table == target.__tablename__]
            remote = [c for c in target.__columns__.values() if c.fk and c.fk.table == self.owner.__tablename__]
            if not is_list and len(local) == 1:
                self.kind, self.fk = "m2o", local[0]
            elif remote:
                if len(remote) > 1:
                    partner = target.__relationships__.get(self.back_populates) if self.back_populates else None
                    if not (partner and partner.foreign_keys):
                        raise TypeError(f"{self.owner.__name__}.{self.name}: several foreign keys, set foreign_keys")
                    remote = [target.__columns__[partner.foreign_keys[0].name]]
                self.kind, self.fk = ("o2m" if is_list else "o2o"), remote[0]
            else:
                raise TypeError(f"{self.owner.__name__}.{self.name}: no foreign key links it to {target.__name__}")
        self.order = []
        if self.order_by_arg:
            for part in str(self.order_by_arg).split(","):
                part = part.strip()
                desc_ = part.endswith(".desc()")
                cname = part.replace(".desc()", "").split(".")[-1]
                self.order.append((target.__columns__[cname], desc_))
        self._resolved = True

    # instance access
    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        self._resolve()
        st = _state(obj)
        if self.kind == "m2o":
            fk_val = obj.__dict__.get(self.fk.name)
            cached = st.rel_cache.get(self.name)
            if fk_val is None:  # not set, or linked to a parent that gets its id at the next flush
                return cached if cached is not None and st.links.get(self.fk.name) is cached else None
            if cached is not None and cached._pk == fk_val:
                return cached
            val = _session_for(obj).get(self.target, fk_val)
            if val is not None:
                st.rel_cache[self.name] = val
            return val
        if self.name in st.rel_cache:
            return st.rel_cache[self.name]
        children = self._load_children(obj)
        if self.kind == "o2m":
            val = InstrumentedList(obj, self, children)
        else:
            val = children[0] if children else None
        st.rel_cache[self.name] = val
        return val

    def _load_children(self, obj):
        st = _state(obj)
        pk = obj._pk
        if not st.persistent or pk is None:
            return []
        stmt = select(self.target).where(self.fk == pk)
        if self.order:
            stmt = stmt.order_by(*[(c.desc() if d else c) for c, d in self.order])
        return _session_for(obj).scalars(stmt).all()

    def __set__(self, obj, value):
        self._resolve()
        st = _state(obj)
        if self.kind == "m2o":
            st.rel_cache[self.name] = value
            if value is None:
                obj.__dict__[self.fk.name] = None
                st.links.pop(self.fk.name, None)
            else:
                _link(value, obj, self.fk.name)
                if st.session is not None:
                    st.session.add(value)
            return
        if self.kind == "o2o":
            old = self.__get__(obj) if st.persistent else st.rel_cache.get(self.name)
            if old is not None and old is not value and self.delete_orphan and st.session is not None:
                st.session.delete(old)
            st.rel_cache[self.name] = value
            if value is not None:
                _link(obj, value, self.fk.name)
                if st.session is not None:
                    st.session.add(value)
            return
        current = self.__get__(obj)
        new_items = list(value or [])
        for old in list(current):
            if not any(old is n for n in new_items):
                current.remove(old)
        for n in new_items:
            if not any(n is c for c in current):
                current.append(n)


def _link(parent, child, fk_name):
    """child.<fk_name> = parent's primary key, now or (if the parent has no id yet) at flush."""
    pk = parent._pk
    cst = _state(child)
    if pk is not None and _state(parent).persistent:
        child.__dict__[fk_name] = pk
        cst.links.pop(fk_name, None)
    else:
        cst.links[fk_name] = parent


# Session used to lazy-load relationships of an object whose own session was closed (set by app.database).
fallback_session_factory = None


def _session_for(obj) -> "Session":
    sess = _state(obj).session
    if sess is None:
        if fallback_session_factory is None:
            raise RuntimeError(f"{obj!r} is not attached to a session")
        sess = fallback_session_factory()
    return sess


def _annotation_text(owner, name) -> str:
    try:
        import annotationlib
        ann = annotationlib.get_annotations(owner, format=annotationlib.Format.STRING)
    except ImportError:  # Python < 3.14
        ann = {k: str(v) for k, v in owner.__dict__.get("__annotations__", {}).items()}
    return str(ann.get(name, ""))


class InstrumentedList(list):
    def __init__(self, owner, rel, items):
        super().__init__(items)
        self._owner, self._rel = owner, rel

    def _adopt(self, child):
        _link(self._owner, child, self._rel.fk.name)
        sess = _state(self._owner).session
        if sess is not None:
            sess.add(child)

    def _orphan(self, child):
        if self._rel.delete_orphan:
            sess = _state(self._owner).session or _state(child).session
            if sess is not None:
                sess.delete(child)
        else:
            child.__dict__[self._rel.fk.name] = None

    def append(self, child):
        self._adopt(child)
        super().append(child)

    def insert(self, i, child):
        self._adopt(child)
        super().insert(i, child)

    def extend(self, children):
        for c in children:
            self.append(c)

    def remove(self, child):
        for i, c in enumerate(self):
            if c is child:
                del self[i]
                self._orphan(child)
                return
        raise ValueError("not in list")

    def pop(self, i=-1):
        child = super().pop(i)
        self._orphan(child)
        return child

    def clear(self):
        while self:
            self.pop()


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


# --------------------------------------------------------------------------- session

class Session:
    """Unit of work over one MongoDB database (same role as sqlalchemy.orm.Session, autoflush off)."""

    def __init__(self, database):
        self.database = database
        self._identity: dict[tuple, Base] = {}
        self._new: list[Base] = []
        self._deleted: list[Base] = []

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
