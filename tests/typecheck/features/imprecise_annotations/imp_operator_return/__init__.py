"""Feature test: operator results annotated or held less precisely than the stubs.

`-> set[str]` (or `typing.Set[str]`) on execute, invoke or modal is the parent's `set[Literal[...]]` with its names
widened to `str`: the method is typed as the parent's, so its returns are still checked name by name, and the
annotation is reported once (blender-imprecise-operator-return). A result set held in a variable is a `set[str]`
(a variable gives its set display no type context): it is accepted and reported at the return. A name that is not
a result stays an error (Blender raises "incompatible return value"; `{'OPERATOR_CANCELLED'}` in a set display
included)."""

from typing import Set

import bpy
from bpy.types import Operator


class IMP_OPERATOR_RETURN_OT_set_str(Operator):
    bl_idname = "imp_operator_return.set_str"
    bl_label = "set[str]"

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"FINISHED"}

    def invoke(self, context, event) -> Set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return self.execute(context)

    def modal(self, context, event) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"FINSHED"}  # ty: ignore[invalid-return-type]


class IMP_OPERATOR_RETURN_OT_follow_on(Operator):
    bl_idname = "imp_operator_return.follow_on"
    bl_label = "Follow-on"

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"CANCELLED"}

    def invoke(self, context, event):
        return self.execute(context)  # the parent's result type: fine


class IMP_OPERATOR_RETURN_OT_variable(Operator):
    bl_idname = "imp_operator_return.variable"
    bl_label = "Variable"

    def execute(self, context):
        ret = {"CANCELLED"}
        if bpy.app.background:
            ret = {"FINISHED"}
        return ret  # ty: ignore[blender-imprecise-operator-return]

    def invoke(self, context, event):
        return {"OPERATOR_CANCELLED"}  # ty: ignore[invalid-return-type]


class ResultMixin:
    """Declares Blender's method with a loose result type so that it type-checks on its own."""

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        return {"FINISHED"}


class IMP_OPERATOR_RETURN_OT_mixin(ResultMixin, Operator):
    bl_idname = "imp_operator_return.mixin"
    bl_label = "Mixin"


classes = (
    IMP_OPERATOR_RETURN_OT_set_str,
    IMP_OPERATOR_RETURN_OT_follow_on,
    IMP_OPERATOR_RETURN_OT_variable,
    IMP_OPERATOR_RETURN_OT_mixin,
)
register, unregister = bpy.utils.register_classes_factory(classes)
