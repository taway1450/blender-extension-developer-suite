"""Feature test: the Imprecise annotation rules configured for one add-on.

`tests/typecheck/ty.toml` has an `[[overrides]]` entry for this add-on that sets the category
`blender-imprecise-annotations` to `error` and the rule `blender-imprecise-enum-value` to `ignore`: the rule's own
level wins over its category's. An ignored rule still accepts the code, so the enum value below is neither reported
nor an error."""

import bpy
from bpy.types import Operator


class IMP_CONFIG_OT_run(Operator):
    bl_idname = "imp_config.run"
    bl_label = "Run"

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"FINISHED"}


def add_light(name: str, light_type: str) -> None:
    bpy.data.lights.new(name, light_type)  # blender-imprecise-enum-value is ignored here: accepted, not reported


def register():
    bpy.utils.register_class(IMP_CONFIG_OT_run)


def unregister():
    bpy.utils.unregister_class(IMP_CONFIG_OT_run)
