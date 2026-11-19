"""Feature test: a PropertyGroup's `id_data` is the data-block that owns it.

Blender stores a PropertyGroup in the data-block its pointer or collection property is registered on, so its
`id_data` is that data-block: `bpy.types.Armature.slots = CollectionProperty(type=Slot)` makes a `Slot`'s
`id_data` an `Armature`. A group nested in another group's annotations is owned by the outer group's data-blocks,
and one on a struct that is not an ID (a `PoseBone`) by that struct's own `id_data` (an `Object`). A group with
no known owner keeps the stubs' type. Every data-block is its own `id_data`.
"""

from typing import assert_type

import bpy
from bpy.props import CollectionProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Armature, Object, PropertyGroup, Scene

from . import shadowed


class PROPS_ID_DATA_Slot(PropertyGroup):
    """Registered as a collection on Armature."""

    value: IntProperty()

    def siblings(self) -> int:
        assert_type(self.id_data, Armature)
        # The armature's own registered collection, as rigify's action slots read it.
        return len(self.id_data.props_id_data_slots)

    def label_from_index(self, stored: str, _is_set: bool) -> str:
        # A callback that the class body passes to a property of its own class.
        assert_type(self.id_data, Armature)
        return str(len(self.id_data.props_id_data_slots)) + stored

    label: StringProperty(get_transform=label_from_index)


class PROPS_ID_DATA_Inner(PropertyGroup):
    """Nested in PROPS_ID_DATA_Outer, which Scene and Object own."""

    value: IntProperty()

    def owner(self) -> Scene | Object:
        assert_type(self.id_data, Scene | Object)
        return self.id_data


class PROPS_ID_DATA_Outer(PropertyGroup):
    inner: PointerProperty(type=PROPS_ID_DATA_Inner)
    inners: CollectionProperty(type=PROPS_ID_DATA_Inner)


class PROPS_ID_DATA_BoneSettings(PropertyGroup):
    """Registered on PoseBone, whose id_data is the armature Object."""

    value: IntProperty()


class PROPS_ID_DATA_Base(PropertyGroup):
    """Registered on Scene; its subclass on Mesh: a Base method may run on either."""

    value: IntProperty()


class PROPS_ID_DATA_Derived(PROPS_ID_DATA_Base):
    extra: IntProperty()


class PROPS_ID_DATA_Shared(PropertyGroup):
    """Registered on Material and on Scene."""

    value: IntProperty()


class PROPS_ID_DATA_Unowned(PropertyGroup):
    """Registered as a class, but no property points to it: its id_data stays the stubs' own."""

    value: IntProperty()


classes = (
    PROPS_ID_DATA_Slot,
    PROPS_ID_DATA_Inner,
    PROPS_ID_DATA_Outer,
    PROPS_ID_DATA_BoneSettings,
    PROPS_ID_DATA_Base,
    PROPS_ID_DATA_Derived,
    PROPS_ID_DATA_Shared,
    PROPS_ID_DATA_Unowned,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    shadowed.register()
    bpy.types.Armature.props_id_data_slots = CollectionProperty(type=PROPS_ID_DATA_Slot)
    bpy.types.Scene.props_id_data_outer = PointerProperty(type=PROPS_ID_DATA_Outer)
    bpy.types.Object.props_id_data_outer = PointerProperty(type=PROPS_ID_DATA_Outer)
    bpy.types.PoseBone.props_id_data_bone = PointerProperty(type=PROPS_ID_DATA_BoneSettings)
    bpy.types.Scene.props_id_data_base = PointerProperty(type=PROPS_ID_DATA_Base)
    bpy.types.Mesh.props_id_data_derived = PointerProperty(type=PROPS_ID_DATA_Derived)
    bpy.types.Material.props_id_data_shared = PointerProperty(type=PROPS_ID_DATA_Shared)
    bpy.types.Scene.props_id_data_shared = PointerProperty(type=PROPS_ID_DATA_Shared)


def unregister():
    del bpy.types.Scene.props_id_data_shared
    del bpy.types.Material.props_id_data_shared
    del bpy.types.Mesh.props_id_data_derived
    del bpy.types.Scene.props_id_data_base
    del bpy.types.PoseBone.props_id_data_bone
    del bpy.types.Object.props_id_data_outer
    del bpy.types.Scene.props_id_data_outer
    del bpy.types.Armature.props_id_data_slots
    shadowed.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
