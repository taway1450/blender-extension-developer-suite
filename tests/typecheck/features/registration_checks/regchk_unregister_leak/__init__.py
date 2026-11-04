"""Feature test: blender-unregister-mismatch, on what register() adds and unregister() does not remove: classes,
properties on Blender classes, handlers and menu draw functions. Blender does not complain, so this loads."""

import bpy
from bpy.app.handlers import persistent
from bpy.props import IntProperty
from bpy.types import Operator


class REGCHK_UNREGISTER_LEAK_OT_paired(Operator):
    bl_idname = "regchk_unregister_leak.paired"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_UNREGISTER_LEAK_OT_loop(Operator):
    bl_idname = "regchk_unregister_leak.loop"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_UNREGISTER_LEAK_OT_leaked(Operator):
    bl_idname = "regchk_unregister_leak.leaked"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


@persistent
def on_load(filepath, _):
    pass


@persistent
def on_save(filepath, _):
    pass


def draw_menu(self, context):
    self.layout.operator("regchk_unregister_leak.paired")


def draw_leaked_menu(self, context):
    self.layout.operator("regchk_unregister_leak.leaked")


classes = (REGCHK_UNREGISTER_LEAK_OT_loop,)


def register():
    bpy.utils.register_class(REGCHK_UNREGISTER_LEAK_OT_paired)
    bpy.utils.register_class(REGCHK_UNREGISTER_LEAK_OT_leaked)  # ty: ignore[blender-unregister-mismatch]
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.regchk_paired = IntProperty()
    bpy.types.Scene.regchk_leaked = IntProperty()  # ty: ignore[blender-unregister-mismatch]
    bpy.app.handlers.load_post.append(on_load)
    bpy.app.handlers.save_post.append(on_save)  # ty: ignore[blender-unregister-mismatch]
    bpy.types.VIEW3D_MT_object.append(draw_menu)
    bpy.types.VIEW3D_MT_object.append(draw_leaked_menu)  # ty: ignore[blender-unregister-mismatch]


def unregister():
    bpy.types.VIEW3D_MT_object.remove(draw_menu)
    bpy.app.handlers.load_post.remove(on_load)
    del bpy.types.Scene.regchk_paired
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(REGCHK_UNREGISTER_LEAK_OT_paired)
