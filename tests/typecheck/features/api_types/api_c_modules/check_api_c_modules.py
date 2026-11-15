"""Blender's private C modules import: `_cycles`, `_bpy` and `_bpy_hydra` partially typed (every member is Any),
`_freestyle` re-exporting the classes of the documented freestyle modules, so they keep their types. These are stub
facts."""

from __future__ import annotations

from typing import Any, assert_type

import _bpy
import _bpy_hydra
import _cycles
import _freestyle
from _bpy import context_members
from _freestyle import ChainSilhouetteIterator, QuantitativeInvisibilityUP1D, blendRamp
from bpy.types import Scene
from freestyle import chainingiterators, predicates
from freestyle.types import ViewEdge


def partial_modules() -> None:
    assert_type(_cycles.with_osl, Any)  # bare-ok: a stub fact: _cycles has no API docs, its members are Any
    assert_type(_bpy.context_members(), Any)  # bare-ok: a stub fact: _bpy has no API docs, its members are Any
    assert_type(context_members, Any)  # bare-ok: a stub fact: imported from _bpy too
    assert_type(_bpy_hydra.engine_create, Any)  # bare-ok: a stub fact: _bpy_hydra has no API docs, its members are Any


def freestyle_classes(edge: _freestyle.ViewEdge, iterator: ChainSilhouetteIterator) -> None:
    assert_type(edge, ViewEdge)  # bare-ok: a stub fact: a _freestyle class is the freestyle.types one
    assert_type(iterator, chainingiterators.ChainSilhouetteIterator)  # bare-ok: a stub fact: from freestyle.chainingiterators
    assert_type(QuantitativeInvisibilityUP1D(0), predicates.QuantitativeInvisibilityUP1D)  # bare-ok: a stub fact: from freestyle.predicates
    assert_type(_freestyle.getCurrentScene(), Scene)  # bare-ok: a stub fact: its functions keep their types too
    assert_type(blendRamp, Any)  # bare-ok: a stub fact: an undocumented _freestyle function is Any
