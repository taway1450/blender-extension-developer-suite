"""Feature test: an add-on that declares the add-on it relies on (`[tool.blender] uses` in its manifest) reads that
add-on's properties. Its own registration of a name comes first."""

import bpy
from bpy.props import StringProperty
from bpy.types import Object, Operator, Scene


class REGCHK_USES_OT_run(Operator):
    bl_idname = "regchk_uses.run"
    bl_label = "Run"

    def execute(self, context):
        context.scene.regchk_uses_provider.samples += 1
        return {"FINISHED"}


def samples(scene: Scene) -> int:
    return scene.regchk_uses_provider.samples


def count(ob: Object) -> int:
    return ob.regchk_uses_provider_count


def register():
    bpy.utils.register_class(REGCHK_USES_OT_run)
    bpy.types.Object.regchk_uses_label = StringProperty()


def unregister():
    del bpy.types.Object.regchk_uses_label
    bpy.utils.unregister_class(REGCHK_USES_OT_run)
