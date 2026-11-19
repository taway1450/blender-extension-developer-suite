"""Feature test: a `type=` the checker cannot read may store any PropertyGroup of the add-on.

`PROPS_ID_DATA_OPAQUE_Group` is registered on Scene with a `type=` the checker reads, and on Object with one it
cannot (`getattr` on the module), so its owners are unknown: its `id_data` keeps the stubs' type, not `Scene`.
"""

import sys

import bpy
from bpy.props import IntProperty, PointerProperty
from bpy.types import PropertyGroup


class PROPS_ID_DATA_OPAQUE_Group(PropertyGroup):
    value: IntProperty()


def register():
    bpy.utils.register_class(PROPS_ID_DATA_OPAQUE_Group)
    bpy.types.Scene.props_id_data_opaque = PointerProperty(type=PROPS_ID_DATA_OPAQUE_Group)
    bpy.types.Object.props_id_data_opaque = PointerProperty(
        type=getattr(sys.modules[__name__], "PROPS_ID_DATA_OPAQUE_Group"))


def unregister():
    del bpy.types.Object.props_id_data_opaque
    del bpy.types.Scene.props_id_data_opaque
    bpy.utils.unregister_class(PROPS_ID_DATA_OPAQUE_Group)
