"""Feature test: the Implied narrowing rules configured for one add-on.

`tests/typecheck/ty.toml` has an `[[overrides]]` entry for this add-on that sets the category
`blender-implied-narrowings` to `error` and the rule `blender-narrowed-by-menu-prefix` to `ignore`: the rule's own level
wins over its category's. An ignored rule still narrows, so the menu's read below is neither reported nor an error."""

import bpy
from bpy.types import Menu, Panel


class NAR_CONFIG_PT_panel(Panel):
    bl_label = "Config"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[blender-narrowed-by-poll]


class VIEW3D_MT_nar_config(Menu):
    bl_label = "Config"

    def draw(self, context):
        self.layout.prop(context.space_data, "show_gizmo")  # blender-narrowed-by-menu-prefix is ignored here


classes = (NAR_CONFIG_PT_panel, VIEW3D_MT_nar_config)
register, unregister = bpy.utils.register_classes_factory(classes)
