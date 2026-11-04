"""Feature test: blender-register-order. Blender fails to register a class with a PointerProperty or
CollectionProperty to a PropertyGroup that is not registered yet, to add such a property to a Blender class, and
to register a subpanel before its parent panel (each checked on its own in Blender 5.4). Unregistering in the
wrong order works, so it is not reported."""

import bpy
from bpy.props import CollectionProperty, PointerProperty
from bpy.types import Panel, PropertyGroup


class REGCHK_ORDER_Leaf(PropertyGroup):
    pass


class REGCHK_ORDER_Pointer(PropertyGroup):
    leaf: PointerProperty(type=REGCHK_ORDER_Leaf)


class REGCHK_ORDER_Collection(PropertyGroup):
    leaves: CollectionProperty(type=REGCHK_ORDER_Leaf)


class REGCHK_ORDER_Ok(PropertyGroup):
    leaf: PointerProperty(type=REGCHK_ORDER_Leaf)


class REGCHK_ORDER_PT_parent(Panel):
    bl_label = "Parent"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class REGCHK_ORDER_PT_child(Panel):
    bl_label = "Child"
    bl_parent_id = "REGCHK_ORDER_PT_parent"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


classes = (
    REGCHK_ORDER_Pointer,  # ty: ignore[blender-register-order]
    REGCHK_ORDER_Leaf,
    REGCHK_ORDER_Ok,
)


def register():
    bpy.utils.register_class(REGCHK_ORDER_Collection)  # ty: ignore[blender-register-order]
    bpy.types.Scene.regchk_order_leaf = PointerProperty(type=REGCHK_ORDER_Leaf)  # ty: ignore[blender-register-order]
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_class(REGCHK_ORDER_PT_child)  # ty: ignore[blender-register-order]
    bpy.utils.register_class(REGCHK_ORDER_PT_parent)


def unregister():
    for cls in classes:  # wrong order, but Blender accepts it
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(REGCHK_ORDER_PT_parent)
    bpy.utils.unregister_class(REGCHK_ORDER_PT_child)
    del bpy.types.Scene.regchk_order_leaf
    bpy.utils.unregister_class(REGCHK_ORDER_Collection)
