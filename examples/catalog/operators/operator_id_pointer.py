# /// catalog
# title = "A data-block pointer on an operator"
# section = "calls"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_calls"]
#
# [runtime]
# register = "ok"
#
# [[runtime.probe]]
# code = "[p.identifier for p in bpy.ops.operator_id_pointer.run.get_rna_type().properties]"
# expect = "['rna_type', 'before']"
# reason = "the operator has no `target`, nor any property declared after it"
# ///
"""An operator cannot hold a pointer to a data-block (an `Object`, a `Material`): Blender registers the class but
drops that property and every property declared after it. Pass a name instead. The checker reports the property."""

import bpy
from bpy.props import IntProperty, PointerProperty, StringProperty
from bpy.types import Object, Operator

bl_info = {
    "name": "Catalog: a data-block pointer on an operator",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class OPERATOR_ID_POINTER_OT_run(Operator):
    bl_idname = "operator_id_pointer.run"
    bl_label = "Run"

    before: StringProperty()
    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-operator-property]
    after: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(OPERATOR_ID_POINTER_OT_run)


def unregister():
    bpy.utils.unregister_class(OPERATOR_ID_POINTER_OT_run)
