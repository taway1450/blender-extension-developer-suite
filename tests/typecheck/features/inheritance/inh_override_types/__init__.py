"""Feature test: overrides Blender accepts (the number of parameters is right) but whose types do not fit the
parent. Explicit annotations that are incompatible are ty's invalid-method-override; an unannotated callback whose
return value does not fit the parent's return type is invalid-return-type (Blender raises "incompatible return
value" when it calls execute, invoke or modal; checked in Blender 5.4). Blender turns any poll result into a bool,
so poll may return any value. Compatible annotations (a wider parameter, a narrower return) are fine."""

from typing import Literal

import bpy
from bpy.types import Context, Operator


class INH_OVERRIDE_TYPES_OT_annotations(Operator):
    bl_idname = "inh_override_types.annotations"
    bl_label = "Annotations"

    def execute(self, context: int):  # ty: ignore[invalid-method-override]
        return {"FINISHED"}

    def invoke(self, context, event) -> str:  # ty: ignore[invalid-method-override]
        return "FINISHED"

    def draw(self, context: Context | None):  # wider than the parent: fine
        pass

    def check(self, context) -> Literal[True]:  # narrower than the parent: fine
        return True


class INH_OVERRIDE_TYPES_OT_returns(Operator):
    bl_idname = "inh_override_types.returns"
    bl_label = "Returns"

    @classmethod
    def poll(cls, context):
        return context.active_object  # any value: Blender takes its truth value

    def execute(self, context):
        return {"DONE"}  # ty: ignore[invalid-return-type]

    def invoke(self, context, event):
        return "FINISHED"  # ty: ignore[invalid-return-type]

    def modal(self, context, event):
        return ["FINISHED"]  # ty: ignore[invalid-return-type]


class INH_OVERRIDE_TYPES_OT_no_return(Operator):
    bl_idname = "inh_override_types.no_return"
    bl_label = "No return"

    def execute(self, context):  # ty: ignore[invalid-return-type]
        print("forgot to return a set")


classes = (INH_OVERRIDE_TYPES_OT_annotations, INH_OVERRIDE_TYPES_OT_returns, INH_OVERRIDE_TYPES_OT_no_return)
register, unregister = bpy.utils.register_classes_factory(classes)
