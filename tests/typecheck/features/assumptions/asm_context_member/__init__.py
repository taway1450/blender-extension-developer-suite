"""Feature test: outside a Blender callback, `scene`, `view_layer`, `tool_settings` and `collection` of a Context are
the window's or the loaded file's in ordinary use (a timer, an app handler, a helper, a test, a preset); `collection`
falls back to the scene's master collection, so it is None exactly when `scene` is. The checker takes them as not
None and reports the read under blender-assumed-context-member. Inside an Operator that a FileHandler names as its
`bl_import_operator`, Blender's collection importer calls it with no scene, so `scene`, `tool_settings` and
`collection` are reported there too. The assert_type calls are no-ops at runtime; nothing here runs while the add-on is imported."""

from typing import assert_type

import bpy
from bpy.app.handlers import persistent
from bpy.types import (BlendData, Collection, Context, FileHandler, Object, Operator, Panel, Scene, ToolSettings, ViewLayer,
                       Window)


def frame_of(context: Context) -> int:
    assert_type(context.scene, Scene)  # ty: ignore[blender-assumed-context-member]
    assert_type(context.view_layer, ViewLayer)  # ty: ignore[blender-assumed-context-member]
    assert_type(context.tool_settings, ToolSettings)  # ty: ignore[blender-assumed-context-member]
    assert_type(context.collection, Collection)  # ty: ignore[blender-assumed-context-member]
    assert_type(context.blend_data, BlendData | None)  # bare-ok: not an assumed member
    assert_type(context.window, Window | None)  # bare-ok: not an assumed member
    return context.scene.frame_current  # ty: ignore[blender-assumed-context-member]


def current_frame() -> int:
    scene = bpy.context.scene  # ty: ignore[blender-assumed-context-member]
    assert_type(scene, Scene)
    return scene.frame_current


def tested() -> None:
    if bpy.context.scene is None:  # tested for None only: not reported
        return
    if bpy.context.view_layer:  # tested for truth only: not reported
        print("view layer")


class Exporter:
    """A plain class: its methods are no Blender callbacks."""

    def frame(self) -> int:
        return bpy.context.scene.frame_current  # ty: ignore[blender-assumed-context-member]


@persistent
def on_load_post(_filepath) -> None:
    print(bpy.context.scene.name)  # ty: ignore[blender-assumed-context-member]


def on_timer() -> None:
    print(bpy.context.view_layer.name)  # ty: ignore[blender-assumed-context-member]


class ASM_CONTEXT_MEMBER_PT_panel(Panel):
    bl_label = "Assumed context member"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        self.layout.label(text=context.scene.name)  # a callback: Guaranteed, not reported

        def later():
            return context.scene.name  # ty: ignore[blender-assumed-context-member]

        self.layout.label(text=later())


class ASM_CONTEXT_MEMBER_OT_import(Operator):
    bl_idname = "asm_context_member.import_thing"
    bl_label = "Import thing"

    def execute(self, context):
        assert_type(context.scene, Scene)  # ty: ignore[blender-assumed-context-member]
        assert_type(context.tool_settings, ToolSettings)  # ty: ignore[blender-assumed-context-member]
        assert_type(context.collection, Collection)  # ty: ignore[blender-assumed-context-member]
        assert_type(context.view_layer, ViewLayer)  # crashes rather than None with no scene: not reported
        return {"FINISHED"}


class ASM_CONTEXT_MEMBER_OT_other(Operator):
    bl_idname = "asm_context_member.other"
    bl_label = "Other"

    def execute(self, context):
        assert_type(context.scene, Scene)  # no FileHandler names it: Guaranteed, not reported
        context.collection.objects.link(context.object)  # ty: ignore[invalid-argument-type]
        return {"FINISHED"}


class ASM_CONTEXT_MEMBER_FH_thing(FileHandler):
    bl_label = "Thing"
    bl_import_operator = "asm_context_member.import_thing"
    bl_file_extensions = ".thing"


def helper_unannotated(context) -> None:
    print(context.scene)  # an unannotated parameter is Unknown: nothing to narrow


def active(context: Context) -> Object | None:
    return context.object  # a dynamic member: not assumed


classes = (ASM_CONTEXT_MEMBER_PT_panel, ASM_CONTEXT_MEMBER_OT_import, ASM_CONTEXT_MEMBER_OT_other,
           ASM_CONTEXT_MEMBER_FH_thing)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.timers.register(on_timer, first_interval=3600.0)


def unregister():
    if bpy.app.timers.is_registered(on_timer):
        bpy.app.timers.unregister(on_timer)
    bpy.app.handlers.load_post.remove(on_load_post)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
