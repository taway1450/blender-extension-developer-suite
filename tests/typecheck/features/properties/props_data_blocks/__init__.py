"""Feature test: Property hosts that reject a pointer to a data-block (an ID type such as Object).

Blender stores the properties of these hosts where data-block pointers are not allowed (the struct flag
STRUCT_NO_DATABLOCK_IDPROPERTIES): an Operator's or Macro's properties, a Gizmo's, add-on and key-config
preferences, and a UIList. Blender rejects the pointer with a ValueError ("doesn't support data-block
properties"): registering the preferences or the UIList raises it, while an Operator, Macro or Gizmo prints it and
registers without the pointer. So register() registers only the hosts that accept the pointer (Blender 5.4), and
the probes in _expected/runtime.toml register each rejecting class on its own. The Gizmo's properties are not
reachable from its class, so it has no probe; registering it prints the same ValueError.
"""

import bpy
from bpy.props import IntProperty, PointerProperty
from bpy.types import (AddonPreferences, Gizmo, KeyConfigPreferences, Macro, Node, Object, Operator, PropertyGroup,
                       UIList)


class PROPS_DATA_BLOCKS_Group(PropertyGroup):
    target: PointerProperty(type=Object)


class PROPS_DATA_BLOCKS_Node(Node):
    bl_idname = "PROPS_DATA_BLOCKS_Node"
    bl_label = "Feature test node"

    target: PointerProperty(type=Object)


class PROPS_DATA_BLOCKS_OT_operator(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "props_data_blocks.operator"
    bl_label = "Operator"

    count: IntProperty()
    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-operator-property]

    def execute(self, context):
        return {"FINISHED"}


class PROPS_DATA_BLOCKS_OT_macro(Macro):  # ty: ignore[blender-unregistered-class]
    bl_idname = "props_data_blocks.macro"
    bl_label = "Macro"

    count: IntProperty()
    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-operator-property]


class PROPS_DATA_BLOCKS_Preferences(AddonPreferences):  # ty: ignore[blender-unregistered-class]
    bl_idname = __package__

    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-property]


class PROPS_DATA_BLOCKS_KeyConfigPreferences(KeyConfigPreferences):  # ty: ignore[blender-unregistered-class]
    bl_idname = "PROPS_DATA_BLOCKS_keyconfig"

    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-property]


class PROPS_DATA_BLOCKS_UL_list(UIList):  # ty: ignore[blender-unregistered-class]
    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-property]

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if isinstance(item, bpy.types.ID):
            layout.label(text=item.name)


class PROPS_DATA_BLOCKS_GT_gizmo(Gizmo):  # ty: ignore[blender-unregistered-class]
    bl_idname = "PROPS_DATA_BLOCKS_GT_gizmo"

    count: IntProperty()
    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-property]

    def draw(self, context):
        pass


classes = (PROPS_DATA_BLOCKS_Group, PROPS_DATA_BLOCKS_Node)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
