"""The style of the annotation does not change the property; class attributes are not properties."""

from __future__ import annotations

from typing import assert_type

from .future_annotations import PROPS_STYLES_Future, PROPS_STYLES_Later
from .inheritance import (PROPS_STYLES_Base, PROPS_STYLES_Child, PROPS_STYLES_MixinFirst, PROPS_STYLES_MixinLast,
                          PROPS_STYLES_Override)
from .plain_annotations import PROPS_STYLES_Plain


def plain(p: PROPS_STYLES_Plain) -> None:
    assert_type(p.count, int)
    assert_type(p.quoted, bool)


def future(f: PROPS_STYLES_Future) -> None:
    assert_type(f.later, PROPS_STYLES_Later)
    assert_type(f.later.ratio, float)
    assert_type(f.factor, float)


def inherited(b: PROPS_STYLES_Base, c: PROPS_STYLES_Child, o: PROPS_STYLES_Override, m: PROPS_STYLES_MixinFirst,
              last: PROPS_STYLES_MixinLast) -> None:
    assert_type(b.base_value, int)
    assert_type(c.base_value, int)
    assert_type(c.child_value, float)
    assert_type(o.base_value, str)
    assert_type(m.count, int)
    assert_type(m.label, str)
    assert_type(m.own, float)
    assert_type(last.count, int)


def class_level() -> None:
    # Registration turns annotations into RNA properties; the class itself has no such attribute.
    PROPS_STYLES_Base.base_value  # ty: ignore[unresolved-attribute]  # oracle-skip: a stub cannot make class-level access an error
    PROPS_STYLES_Plain.count  # ty: ignore[unresolved-attribute]  # oracle-skip: a stub cannot make class-level access an error
