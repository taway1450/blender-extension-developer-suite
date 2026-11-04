"""Feature test: blender-duplicate-registration and blender-registered-base. A registered subclass that does not
set its own bl_idname inherits the parent's, so registering it replaces the parent (Blender only prints "has been
registered before, unregistering previous"); unregistering the parent then fails. What the operator then does
depends on the version (checked at runtime): Blender 4.2 runs the subclass's execute, 5.4 runs nothing and still
returns {"FINISHED"}. The operator has the subclass's properties."""

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Operator


class INH_INHERITED_IDNAME_OT_parent(Operator):
    bl_idname = "inh_inherited_idname.run"
    bl_label = "Parent"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class INH_INHERITED_IDNAME_OT_child(INH_INHERITED_IDNAME_OT_parent):  # ty: ignore[blender-duplicate-registration, blender-registered-base]
    bl_label = "Child"

    label: StringProperty()


classes = (INH_INHERITED_IDNAME_OT_parent, INH_INHERITED_IDNAME_OT_child)
register, unregister = bpy.utils.register_classes_factory(classes)
