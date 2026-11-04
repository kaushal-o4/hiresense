"""Declarative models (Base), relationships and per-object state."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .coltypes import _to_storage
from .expressions import Column
from .statements import select

if TYPE_CHECKING:
    from .session import Session

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


def set_fallback_session_factory(factory) -> None:
    global fallback_session_factory
    fallback_session_factory = factory


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
