# /// catalog
# title = "Rule levels per add-on"
# section = "strictness"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["imprecise_annotations"]
#
# [evidence]
# addon = "imprecise_annotations/imp_config"
# rule = "blender-imprecise-operator-return"
# lenient = "error"
# default = "error"
# strict = "error"
# ///
"""A level set for a Rule category or a single rule wins over the Strictness preset, and ty's `[[overrides]]` table
in `ty.toml` sets it for one add-on's files: `blender-imprecise-annotations = "error"` makes the whole category an
error there under every preset, and a rule set on its own, such as `blender-imprecise-enum-value = "ignore"`, wins
over its category. The catalog sets no override, so the lines below are reported at the default level."""

import bpy
from bpy.types import Operator


class RunLevels(Operator):
    bl_idname = "tooling.run_levels"
    bl_label = "Run"

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"FINISHED"}


def add_light(name: str, light_type: str) -> None:
    bpy.data.lights.new(name, light_type)  # ty: ignore[blender-imprecise-enum-value]
