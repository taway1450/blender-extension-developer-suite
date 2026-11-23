"""A PropertyGroup's id_data is the data-block its registrations put it in; a data-block's is itself."""

from __future__ import annotations

from typing import assert_type

from bpy.types import ID, Armature, Curve, Material, Mesh, Object, Scene

from . import (PROPS_ID_DATA_Base, PROPS_ID_DATA_BoneSettings, PROPS_ID_DATA_Derived, PROPS_ID_DATA_Inner,
               PROPS_ID_DATA_Outer, PROPS_ID_DATA_Shared, PROPS_ID_DATA_Slot)
from .shadowed import Text as ShadowedText


def registered(slot: PROPS_ID_DATA_Slot, shared: PROPS_ID_DATA_Shared, bone: PROPS_ID_DATA_BoneSettings) -> None:
    assert_type(slot.id_data, Armature)
    assert_type(shared.id_data, Material | Scene)
    assert_type(bone.id_data, Object)


def nested(outer: PROPS_ID_DATA_Outer, inner: PROPS_ID_DATA_Inner) -> None:
    assert_type(outer.id_data, Scene | Object)
    assert_type(inner.id_data, Scene | Object)


def subclasses(base: PROPS_ID_DATA_Base, derived: PROPS_ID_DATA_Derived) -> None:
    # A Base may be a Derived, so it may be in a Mesh; a Derived is never stored where a Base is.
    assert_type(base.id_data, Scene | Mesh)
    assert_type(derived.id_data, Mesh)


def data_blocks(obj: Object, scene: Scene, armature: Armature, data_block: ID) -> None:
    assert_type(obj.id_data, Object)
    assert_type(scene.id_data, Scene)
    assert_type(armature.id_data, Armature)
    assert_type(data_block.id_data, ID)  # bare-ok: any data-block is still an ID


def shadowed(text: ShadowedText) -> None:
    # In register(), `Text` is the group: the module rebinds the imported bpy.types.Text before it runs.
    assert_type(text.id_data, Curve)
