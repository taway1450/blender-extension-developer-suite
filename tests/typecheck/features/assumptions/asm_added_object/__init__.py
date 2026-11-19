"""Feature test: `bpy.ops.mesh.primitive_cube_add()` and the other `*_add` operators add an object, select it and make
it the active one, so code that calls one reads the new object as `context.object` or `context.active_object`. Whether
the call succeeded is not visible (an operator returns `{'CANCELLED'}` rather than raise when its poll fails in some
contexts), so the checker takes the read as not None after such a call earlier in the same function, or the same
module-level script, and reports it under blender-assumed-added-object. The read is the Type tag view of the object
the operator adds (`mesh.primitive_*_add` a mesh, `object.add(type='LATTICE')` a lattice, `object.add()` an empty),
so `.data` is that object's data; an operator whose object type the call doesn't show (`object.effector_add`,
`object.add(type=kind)`) and a call in a branch the read is not in give `Object`. A read before the call, in another function and after another operator keeps the stub type. The
assert_type calls are no-ops at runtime."""

from typing import Any, Literal, assert_type

import bpy
from bpy.types import Camera, Context, Lattice, Light, Mesh, Object, Operator, TextCurve


def add_cube(context: Context) -> Object:
    print(context.object)  # before the call: Object | None, only printed
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = context.object  # ty: ignore[blender-assumed-added-object]
    assert_type(cube.type, Literal['MESH'])  # the view of a mesh object
    assert_type(cube.data, Mesh)
    cube.name = "Cube"
    bpy.ops.object.add(type='EMPTY')
    assert_type(context.active_object.type, Literal['EMPTY'])  # ty: ignore[blender-assumed-added-object]
    if context.active_object is None:  # tested for None only: not reported
        raise RuntimeError("no object")
    return cube


def add_more(context: Context) -> None:
    bpy.ops.object.text_add()
    text = context.object  # ty: ignore[blender-assumed-added-object]
    assert_type(text.type, Literal['FONT'])
    assert_type(text.data, TextCurve)
    bpy.ops.object.add(type='LATTICE')
    assert_type(context.object.data, Lattice)  # ty: ignore[blender-assumed-added-object]
    bpy.ops.object.camera_add()
    assert_type(context.object.data, Camera)  # ty: ignore[blender-assumed-added-object]
    bpy.ops.object.effector_add(type='GUIDE')
    assert_type(context.object, Object)  # ty: ignore[blender-assumed-added-object]


def add_unknown(context: Context, kind: Literal['LATTICE', 'CAMERA'], options: dict[str, Any], cube: bool) -> None:
    bpy.ops.object.add(type=kind)
    assert_type(context.object, Object)  # ty: ignore[blender-assumed-added-object]
    bpy.ops.object.add(**options)
    assert_type(context.object, Object)  # ty: ignore[blender-assumed-added-object]
    bpy.ops.object.camera_add()
    if cube:
        bpy.ops.mesh.primitive_cube_add()
    assert_type(context.object, Object)  # ty: ignore[blender-assumed-added-object]


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
        assert_type(light.type, Literal['LIGHT'])
        assert_type(light.data, Light)
        light.location.z = 3.0
        return {'FINISHED'}


classes = (ASM_ADDED_OBJECT_OT_add,)
register, unregister = bpy.utils.register_classes_factory(classes)
