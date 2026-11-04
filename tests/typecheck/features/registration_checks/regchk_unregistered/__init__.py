"""Feature test: blender-unregistered-class, on Blender classes the addon never registers, also in modules that are
imported without being registered and in modules nobody imports. Not reported: base classes that registered
classes derive from, mixins and registered classes."""

import bpy
from bpy.props import IntProperty
from bpy.types import AddonPreferences, Menu, Operator, Panel, PropertyGroup, UIList

from . import imported_only


class _ExecuteMixin:
    def execute(self, context):
        return {"FINISHED"}


class REGCHK_UNREGISTERED_PT_base(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Checks"


class REGCHK_UNREGISTERED_OT_base(Operator):
    bl_label = "Base"

    steps: IntProperty()


class REGCHK_UNREGISTERED_OT_used(_ExecuteMixin, REGCHK_UNREGISTERED_OT_base):
    bl_idname = "regchk_unregistered.used"
    bl_label = "Used"


class REGCHK_UNREGISTERED_PT_used(REGCHK_UNREGISTERED_PT_base):
    bl_label = "Used"

    def draw(self, context):
        pass


class REGCHK_UNREGISTERED_OT_forgotten(_ExecuteMixin, Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "regchk_unregistered.forgotten"
    bl_label = "Forgotten"


class REGCHK_UNREGISTERED_PT_forgotten(REGCHK_UNREGISTERED_PT_base):  # ty: ignore[blender-unregistered-class]
    bl_label = "Forgotten"

    def draw(self, context):
        pass


class REGCHK_UNREGISTERED_MT_forgotten(Menu):  # ty: ignore[blender-unregistered-class]
    bl_label = "Forgotten"

    def draw(self, context):
        pass


class REGCHK_UNREGISTERED_UL_forgotten(UIList):  # ty: ignore[blender-unregistered-class]
    pass


class REGCHK_UNREGISTERED_Forgotten(PropertyGroup):  # ty: ignore[blender-unregistered-class]
    value: IntProperty()


class REGCHK_UNREGISTERED_Preferences(AddonPreferences):  # ty: ignore[blender-unregistered-class]
    bl_idname = __package__


def register():
    bpy.utils.register_class(REGCHK_UNREGISTERED_OT_used)
    bpy.utils.register_class(REGCHK_UNREGISTERED_PT_used)
    imported_only.helper()


def unregister():
    bpy.utils.unregister_class(REGCHK_UNREGISTERED_PT_used)
    bpy.utils.unregister_class(REGCHK_UNREGISTERED_OT_used)
