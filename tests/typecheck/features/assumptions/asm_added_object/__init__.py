"""Feature test: `bpy.ops.mesh.primitive_cube_add()` and the other `*_add` operators add an object, select it and make
it the active one, so code that calls one reads the new object as `context.object` or `context.active_object`. Whether
the call succeeded is not visible (an operator returns `{'CANCELLED'}` rather than raise when its poll fails in some
contexts), so the checker takes the read as not None after such a call earlier in the same function, or the same
module-level script, and reports it under blender-assumed-added-object. A read before the call, in another function
and after another operator keeps the stub type. The assert_type calls are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Context, Object, Operator


def add_cube(context: Context) -> Object:
    print(context.object)  # before the call: Object | None, only printed
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = context.object  # ty: ignore[blender-assumed-added-object]
    assert_type(cube, Object)
    cube.name = "Cube"
    bpy.ops.object.add(type='EMPTY')
    assert_type(context.active_object, Object)  # ty: ignore[blender-assumed-added-object]
    if context.active_object is None:  # tested for None only: not reported
        raise RuntimeError("no object")
    return cube


def other(context: Context) -> None:
    assert_type(context.object, Object | None)  # bare-ok: no `*_add` operator called in this function


def selected(context: Context) -> None:
    bpy.ops.object.select_all(action='SELECT')
    assert_type(context.active_object, Object | None)  # bare-ok: not an `*_add` operator


class ASM_ADDED_OBJECT_OT_add(Operator):
    bl_idname = "asm_added_object.add"
    bl_label = "Add"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.light_add(type='POINT')
        light = context.active_object  # ty: ignore[blender-assumed-added-object]
        light.location.z = 3.0
        return {'FINISHED'}


classes = (ASM_ADDED_OBJECT_OT_add,)
register, unregister = bpy.utils.register_classes_factory(classes)
