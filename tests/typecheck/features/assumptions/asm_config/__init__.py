"""Feature test: the Assumption rules configured for one add-on.

`tests/typecheck/ty.toml` has an `[[overrides]]` entry for this add-on that sets the category `blender-assumptions` to
`error`, the rule `blender-assumed-context-member` to `ignore` and the five rules of spec #123
(`blender-assumed-internal-operator`, `-editor-member`, `-preset-context`, `-added-object`, `-subclass-member`) to
`warn`: the rule's own level wins over its category's. An ignored rule still narrows, so the helper's read below
is neither reported nor an error. The preset is in presets/asm_config/."""

import bpy
from bpy.types import Context, Menu, Object, Operator, UIList


def frame() -> int:
    return bpy.context.scene.frame_current  # blender-assumed-context-member is ignored here


class ASM_CONFIG_UL_items(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name")  # ty: ignore[blender-assumed-list-item]


class ASM_CONFIG_OT_internal(Operator):
    bl_idname = "asm_config.internal"
    bl_label = "Internal"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        print(context.object.name)  # ty: ignore[blender-assumed-internal-operator]
        return {'FINISHED'}


class ASM_CONFIG_MT_menu(Menu):
    bl_label = "Config"

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'VIEW_3D'  # ty: ignore[blender-assumed-editor-member]

    def draw(self, context):
        self.layout.label(text="Config")


def add_cube(context: Context) -> str:
    bpy.ops.mesh.primitive_cube_add()
    return context.object.name  # ty: ignore[blender-assumed-added-object]


def first_target(ob: Object) -> Object | None:
    return ob.constraints[0].target  # ty: ignore[blender-assumed-subclass-member]


classes = (ASM_CONFIG_UL_items, ASM_CONFIG_OT_internal, ASM_CONFIG_MT_menu)
register, unregister = bpy.utils.register_classes_factory(classes)
