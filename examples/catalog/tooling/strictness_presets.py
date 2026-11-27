# /// catalog
# title = "The Strictness presets"
# section = "strictness"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["imprecise_annotations"]
#
# [evidence]
# addon = "imprecise_annotations/imp_strictness"
# rule = "blender-imprecise-operator-return"
# lenient = "ignore"
# default = "warn"
# strict = "error"
# ///
"""The checker sorts its Blender rules into Rule categories, and `strictness` in the `[blender]` table of `ty.toml`
sets the level of every category at once: `"lenient"`, `"default"` or `"strict"`. An Imprecise annotation, such as
`-> set[str]` on `execute`, is right in Blender but less precise than the stubs: lenient ignores it, the default
warns, and strict, for code that wants the precise annotation, makes it an error."""

from bpy.types import Operator


class Run(Operator):
    bl_idname = "tooling.run_presets"
    bl_label = "Run"

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"FINISHED"}
