"""Legacy Renamer: rename objects by pattern. Written the way add-ons were written before extensions."""

# demo: addon_discovery
bl_info = {
    "name": "Legacy Renamer",
    "author": "Blender Extension Developer Suite",
    "version": (1, 2, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Rename",
    "description": "Rename objects by prefix, number and find/replace rules",
    "category": "Object",
}

# Reloading the add-on runs this file again in its old namespace, where the submodules are still bound.
# Ruff cannot know that, so it reports them as undefined names.
if "bpy" in locals():
    import importlib

    importlib.reload(props)  # noqa: F821
    importlib.reload(ops)  # noqa: F821
    importlib.reload(ui)  # noqa: F821
else:
    from . import ops, props, ui

import bpy
from bpy.props import PointerProperty, StringProperty


class LegacyRenamerPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    separator: StringProperty(
        name="Separator",
        description="Text between the prefix and the number",
        default="_",
    )

    def draw(self, context):
        self.layout.prop(self, "separator")


classes = (
    props.RenameRule,
    props.RenamerSettings,
    LegacyRenamerPreferences,
    *ops.classes,
    *ui.classes,
)
register_classes, unregister_classes = bpy.utils.register_classes_factory(classes)


def register():
    register_classes()
    # Collections have a color tag since 2.91.
    if bpy.app.version >= (2, 91, 0):
        bpy.utils.register_class(ops.OBJECT_OT_legacy_tag_collections)
    bpy.types.Scene.legacy_renamer = PointerProperty(type=props.RenamerSettings)
    # `unregister()` below forgets this property, so it stays on every object after the add-on is disabled.
    # demo: blender-unregister-mismatch
    bpy.types.Object.legacy_original_name = StringProperty(name="Original Name")


def unregister():
    del bpy.types.Scene.legacy_renamer
    if bpy.app.version >= (2, 91, 0):
        bpy.utils.unregister_class(ops.OBJECT_OT_legacy_tag_collections)
    unregister_classes()
