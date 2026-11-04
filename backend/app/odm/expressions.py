"""Query expressions: columns, comparisons, boolean operators, functions, ordering."""
from __future__ import annotations

import copy
import re

from .coltypes import ForeignKey, Integer, _Type, _cmp_value, _to_storage
from .statements import Select, Subquery

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
