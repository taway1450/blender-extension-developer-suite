"""``bl_rna.properties`` with a string-literal key is the ``Property`` subclass of the attribute of that name: an
enum (or an enum flag) gives ``EnumProperty``, ``bool`` ``BoolProperty``, ``int`` ``IntProperty``, a float or a
``mathutils`` value ``FloatProperty``, ``str`` ``StringProperty``, a collection ``CollectionProperty`` and a struct
``PointerProperty``. A name the class lacks, or a key that is not a literal, keeps the stubs' ``Property``. Reference
stubs cannot type a collection item by its key, so the oracle skips these lines."""

from __future__ import annotations

from typing import assert_type

from bpy.types import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, Keyframe, Object,
                       PointerProperty, Property, StringProperty)

from . import PROPS_RNA_Settings


def builtin(keyframe: Keyframe, obj: Object, key: str) -> None:
    assert_type(Keyframe.bl_rna.properties["interpolation"], EnumProperty)  # oracle-skip: typed by the key
    assert_type(keyframe.bl_rna.properties["select_control_point"], BoolProperty)  # oracle-skip: typed by the key
    assert_type(obj.bl_rna.properties["mode"], EnumProperty)  # oracle-skip: typed by the key
    assert_type(obj.bl_rna.properties["pass_index"], IntProperty)  # oracle-skip: typed by the key
    assert_type(obj.bl_rna.properties["location"], FloatProperty)  # oracle-skip: typed by the key
    assert_type(obj.bl_rna.properties["name"], StringProperty)  # oracle-skip: typed by the key
    assert_type(obj.bl_rna.properties["material_slots"], CollectionProperty)  # oracle-skip: typed by the key
    assert_type(obj.bl_rna.properties["parent"], PointerProperty)  # oracle-skip: typed by the key
    assert_type(obj.bl_rna.properties["no_such_property"], Property)  # oracle-skip: fake-bpy-module types bl_rna `Struct | None` and Blender 5.2's stubs lack it  # bare-ok: a name Object lacks keeps Property
    assert_type(obj.bl_rna.properties[key], Property)  # oracle-skip: fake-bpy-module types bl_rna `Struct | None` and Blender 5.2's stubs lack it  # bare-ok: a key that is not a literal keeps Property


def own(settings: PROPS_RNA_Settings) -> None:
    assert_type(settings.bl_rna.properties["count"], IntProperty)  # oracle-skip: typed by the key
    assert_type(PROPS_RNA_Settings.bl_rna.properties["flags"], EnumProperty)  # oracle-skip: typed by the key
