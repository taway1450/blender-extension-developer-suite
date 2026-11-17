"""Feature test: the `[blender] strictness` presets for the Imprecise annotation rules.

One use of each rule. `check:features` also runs ty on this add-on once per preset (`lenient`, `default`, `strict`)
without its `blender-*` markers, and compares the level of each reported rule with `_expected/strictness.toml`:
`lenient` ignores the Imprecise annotations, `default` warns, `strict` makes them errors."""

import bpy
from bpy.types import Armature, Operator, UIList


class IMP_STRICTNESS_OT_run(Operator):
    bl_idname = "imp_strictness.run"
    bl_label = "Run"

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"FINISHED"}


class IMP_STRICTNESS_UL_bones(UIList):
    def draw_item(self, context, layout, data: Armature, item, icon, active_data, active_property):  # ty: ignore[blender-imprecise-callback-parameter]
        pass


def add_light(name: str, light_type: str) -> None:
    bpy.data.lights.new(name, light_type)  # ty: ignore[blender-imprecise-enum-value]


classes = (IMP_STRICTNESS_OT_run, IMP_STRICTNESS_UL_bones)
register, unregister = bpy.utils.register_classes_factory(classes)
