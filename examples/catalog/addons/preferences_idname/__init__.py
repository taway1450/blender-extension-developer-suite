# /// catalog
# title = "A preferences `bl_idname` that is not the add-on's module"
# section = "preferences"
# status = "handled"
# safeguards = ["typechecker", "blender-runtime"]
# features = ["addon_preferences"]
#
# [evidence]
# addon = "addon_preferences/prefs_bad"
# register = "fails"
# says = "replaces the one before"
# ///
"""Blender finds an add-on's preferences by their `bl_idname`, which must be the add-on's module: `__package__` in
an extension, which is `bl_ext.<repository>.<id>`, not the bare `id`. A class named by the `id`, or by
`__name__.split(".")[0]` (that is `bl_ext`), registers but is never the add-on's preferences. A second class named by
the module replaces the first, so unregistering the add-on fails. The checker reports each."""

import bpy
from bpy.props import IntProperty
from bpy.types import AddonPreferences


class PREFERENCES_IDNAME_Literal(AddonPreferences):
    bl_idname = "preferences_idname"  # ty: ignore[blender-preferences-idname]

    value: IntProperty()


class PREFERENCES_IDNAME_FirstComponent(AddonPreferences):
    bl_idname = __name__.split(".")[0]  # ty: ignore[blender-preferences-idname]

    value: IntProperty()


class PREFERENCES_IDNAME_First(AddonPreferences):
    bl_idname = __package__

    value: IntProperty()


class PREFERENCES_IDNAME_Second(AddonPreferences):
    bl_idname = __package__  # ty: ignore[blender-preferences-idname]

    other: IntProperty()


classes = (
    PREFERENCES_IDNAME_Literal,
    PREFERENCES_IDNAME_FirstComponent,
    PREFERENCES_IDNAME_First,
    PREFERENCES_IDNAME_Second,
)
register, unregister = bpy.utils.register_classes_factory(classes)
