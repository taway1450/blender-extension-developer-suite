"""Classes Blender rejects before or at registration (each checked in Blender 5.4). This module is never imported:
its classes raise TypeError when they are created."""

from __future__ import annotations

from abc import ABC

import bpy
from bpy.types import Mesh, Modifier, Object, Operator, UILayout


class ObjectSubclass(Object):  # a subclass on its own is allowed
    pass


class MeshSubclass(Mesh):
    pass


class ModifierSubclass(Modifier):
    pass


class LayoutSubclass(UILayout):
    pass


def register_unsupported() -> None:
    # Blender: "... does not support registration". The stubs already type register_class with the
    # registrable bases, so this is ty's own invalid-argument-type.
    bpy.utils.register_class(ObjectSubclass)  # ty: ignore[invalid-argument-type]  # bare-ok: stock ty's error must stay: not a registrable base
    bpy.utils.register_class(MeshSubclass)  # ty: ignore[invalid-argument-type]  # bare-ok: stock ty's error must stay: not a registrable base
    bpy.utils.register_class(ModifierSubclass)  # ty: ignore[invalid-argument-type]  # bare-ok: stock ty's error must stay: not a registrable base
    bpy.utils.register_class(LayoutSubclass)  # ty: ignore[invalid-argument-type]  # bare-ok: stock ty's error must stay: not a registrable base


class AbcMixin(ABC):
    pass


class WithAbc(AbcMixin, Operator):  # ty: ignore[conflicting-metaclass]  # oracle-skip: the stubs do not declare Blender's metaclass
    """TypeError: metaclass conflict (Operator's metaclass is bpy's _RNAMeta)."""


class SlotsMixin:
    __slots__ = ("value",)


class WithSlots(SlotsMixin, Operator):  # ty: ignore[instance-layout-conflict]  # oracle-skip: the stubs do not declare the C struct layout
    """TypeError: multiple bases have instance lay-out conflict."""
