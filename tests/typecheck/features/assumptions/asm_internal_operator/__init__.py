"""Feature test: an Internal operator (`'INTERNAL'` in its `bl_options`) is hidden from the operator search, so in
ordinary use only the button, menu entry or key of its own add-on calls it, from where it works. The checker takes the
context members its callbacks read as not None and reports them under blender-assumed-internal-operator. Nothing
stops a script or a user key map from calling it elsewhere, so it is an Assumption. A poll's own check wins (reported
under blender-narrowed-by-poll), the poll itself and helpers get nothing, and an operator without the flag keeps the
stub types. The assert_type calls are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Context, Object, Operator, Screen, Space, Window


class ASM_INTERNAL_OPERATOR_OT_show(Operator):
    bl_idname = "asm_internal_operator.show"
    bl_label = "Show"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-assumed-internal-operator]
        assert_type(context.space_data, Space)  # ty: ignore[blender-assumed-internal-operator]
        areas = context.screen.areas  # ty: ignore[blender-assumed-internal-operator]
        print(len(areas))
        if context.window is None:  # tested for None only: not reported
            return {'CANCELLED'}
        assert_type(context.window, Window)
        return {'FINISHED'}

    def invoke(self, context, event):
        screen = context.screen  # ty: ignore[blender-assumed-internal-operator]
        assert_type(screen, Screen)
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        assert_type(context.object, Object | None)  # bare-ok: the poll is where the operator checks
        return True


class AsmInternalOperatorBase(Operator):
    bl_options = {'INTERNAL'}


class ASM_INTERNAL_OPERATOR_OT_inherited(AsmInternalOperatorBase):
    bl_idname = "asm_internal_operator.inherited"
    bl_label = "Inherited"

    def execute(self, context):
        print(context.object.name)  # ty: ignore[blender-assumed-internal-operator]
        return {'FINISHED'}


class ASM_INTERNAL_OPERATOR_OT_polled(Operator):
    bl_idname = "asm_internal_operator.polled"
    bl_label = "Polled"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        print(context.object.name)  # ty: ignore[blender-narrowed-by-poll]
        return {'FINISHED'}


def helper(context: Context) -> None:
    print(context.object.name)  # ty: ignore[missing-union-attribute]  # bare-ok: a helper is no callback


class ASM_INTERNAL_OPERATOR_OT_public(Operator):
    bl_idname = "asm_internal_operator.public"
    bl_label = "Public"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        assert_type(context.object, Object | None)  # bare-ok: not an Internal operator
        helper(context)
        return {'FINISHED'}


classes = (ASM_INTERNAL_OPERATOR_OT_show, ASM_INTERNAL_OPERATOR_OT_inherited, ASM_INTERNAL_OPERATOR_OT_polled,
           ASM_INTERNAL_OPERATOR_OT_public)
register, unregister = bpy.utils.register_classes_factory(classes)
