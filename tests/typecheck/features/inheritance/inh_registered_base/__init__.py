"""Feature test: blender-registered-base. Registering a subclass of a class that is registered itself silently
breaks the base: Blender detaches the base's Python class (bpy_rna.cc, "Old srna still references us"), so
Blender no longer calls its callbacks. An operator still returns {"FINISHED"} without running execute, a panel or
menu draws nothing, a UI list draws no items, a node can no longer be added; Blender only logs "unable to get Python
class for RNA struct". Unregistering the subclass does not repair it. Registered the other way round (the subclass
first) both work, but Blender's own --debug-python check warns about either order and recommends mixins. Checked
at runtime in Blender 4.2 and 5.4. Property groups have no callbacks and keep working, so they are not reported.
The add-on loads; only the base classes are broken, which check:load confirms (_expected/runtime.toml)."""

import bpy
from bpy.props import IntProperty
from bpy.types import Menu, Node, NodeTree, Operator, Panel, PropertyGroup, UIList


class INH_REGISTERED_BASE_OT_parent(Operator):
    bl_idname = "inh_registered_base.parent"
    bl_label = "Parent"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class INH_REGISTERED_BASE_OT_child(INH_REGISTERED_BASE_OT_parent):  # ty: ignore[blender-registered-base]
    """Registered after the parent: the parent's execute is no longer called."""

    bl_idname = "inh_registered_base.child"
    bl_label = "Child"


class INH_REGISTERED_BASE_OT_late_parent(Operator):
    bl_idname = "inh_registered_base.late_parent"
    bl_label = "Late parent"

    def execute(self, context):
        return {"FINISHED"}


class INH_REGISTERED_BASE_OT_early_child(INH_REGISTERED_BASE_OT_late_parent):  # ty: ignore[blender-registered-base]
    """Registered before its parent: both work, but it depends on the order."""

    bl_idname = "inh_registered_base.early_child"
    bl_label = "Early child"


class INH_REGISTERED_BASE_PT_parent(Panel):
    bl_label = "Parent"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.label(text="parent")


class INH_REGISTERED_BASE_PT_child(INH_REGISTERED_BASE_PT_parent):  # ty: ignore[blender-registered-base]
    bl_label = "Child"


class INH_REGISTERED_BASE_MT_parent(Menu):
    bl_label = "Parent"

    def draw(self, context):
        self.layout.label(text="parent")


class INH_REGISTERED_BASE_MT_child(INH_REGISTERED_BASE_MT_parent):  # ty: ignore[blender-registered-base]
    bl_label = "Child"


class INH_REGISTERED_BASE_UL_parent(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        if isinstance(item, bpy.types.ID):
            layout.label(text=item.name)


class INH_REGISTERED_BASE_UL_child(INH_REGISTERED_BASE_UL_parent):  # ty: ignore[blender-registered-base]
    pass


class INH_REGISTERED_BASE_Tree(NodeTree):
    bl_idname = "INH_REGISTERED_BASE_Tree"
    bl_label = "Registered base tree"
    bl_icon = "NODETREE"


class INH_REGISTERED_BASE_NodeParent(Node):
    bl_idname = "INH_REGISTERED_BASE_NodeParent"
    bl_label = "Parent"


class INH_REGISTERED_BASE_NodeChild(INH_REGISTERED_BASE_NodeParent):  # ty: ignore[blender-registered-base]
    """After this is registered, the parent node can no longer be added."""

    bl_idname = "INH_REGISTERED_BASE_NodeChild"
    bl_label = "Child"


class INH_REGISTERED_BASE_Group(PropertyGroup):
    value: IntProperty()


class INH_REGISTERED_BASE_GroupChild(INH_REGISTERED_BASE_Group):
    extra: IntProperty()


classes = (
    INH_REGISTERED_BASE_OT_parent,
    INH_REGISTERED_BASE_OT_child,
    INH_REGISTERED_BASE_OT_early_child,
    INH_REGISTERED_BASE_OT_late_parent,
    INH_REGISTERED_BASE_PT_parent,
    INH_REGISTERED_BASE_PT_child,
    INH_REGISTERED_BASE_MT_parent,
    INH_REGISTERED_BASE_MT_child,
    INH_REGISTERED_BASE_UL_parent,
    INH_REGISTERED_BASE_UL_child,
    INH_REGISTERED_BASE_Tree,
    INH_REGISTERED_BASE_NodeParent,
    INH_REGISTERED_BASE_NodeChild,
    INH_REGISTERED_BASE_Group,
    INH_REGISTERED_BASE_GroupChild,
)
register, unregister = bpy.utils.register_classes_factory(classes)
