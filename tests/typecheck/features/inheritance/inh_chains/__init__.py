"""Feature test: chains of Blender classes. A registered class may derive from any number of unregistered
classes; it has the properties and callbacks of all of them (checked at runtime in Blender 4.2 and 5.4). Several
registered classes may share a base. The bases themselves are not registered, so they are no operators, panels or
menus. Registering a class *and* its subclass is blender-registered-base (see inh_registered_base); property
groups are the exception."""

import bpy
from bpy.props import FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Menu, Operator, Panel, PropertyGroup


class INH_CHAINS_OT_base(Operator):
    bl_label = "Base"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class INH_CHAINS_OT_middle(INH_CHAINS_OT_base):
    label: StringProperty()


class INH_CHAINS_OT_leaf(INH_CHAINS_OT_middle):
    """Two unregistered bases above it."""

    bl_idname = "inh_chains.leaf"
    bl_label = "Leaf"

    factor: FloatProperty()


class INH_CHAINS_OT_sibling(INH_CHAINS_OT_base):
    bl_idname = "inh_chains.sibling"
    bl_label = "Sibling"


class INH_CHAINS_A(PropertyGroup):
    a: IntProperty()


class INH_CHAINS_B(INH_CHAINS_A):
    b: StringProperty()


class INH_CHAINS_C(INH_CHAINS_B):
    """Registered together with INH_CHAINS_A: allowed for property groups, which have no callbacks."""

    c: FloatProperty()


class INH_CHAINS_PT_base(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chains"

    def draw(self, context):
        self.layout.operator("inh_chains.leaf")


class INH_CHAINS_PT_main(INH_CHAINS_PT_base):
    bl_label = "Main"


class INH_CHAINS_PT_sub(INH_CHAINS_PT_base):
    bl_label = "Sub"
    bl_parent_id = "INH_CHAINS_PT_main"


class INH_CHAINS_MT_base(Menu):
    def draw(self, context):
        self.layout.operator("inh_chains.sibling")


class INH_CHAINS_MT_one(INH_CHAINS_MT_base):
    bl_label = "One"


class INH_CHAINS_MT_two(INH_CHAINS_MT_base):
    bl_label = "Two"


classes = (
    INH_CHAINS_OT_leaf,
    INH_CHAINS_OT_sibling,
    INH_CHAINS_A,
    INH_CHAINS_C,
    INH_CHAINS_PT_main,
    INH_CHAINS_PT_sub,
    INH_CHAINS_MT_one,
    INH_CHAINS_MT_two,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.inh_chains_c = PointerProperty(type=INH_CHAINS_C)


def unregister():
    del bpy.types.Scene.inh_chains_c
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
