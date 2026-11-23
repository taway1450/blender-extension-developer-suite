"""Feature test: an add-on reads the properties of the add-ons its manifest declares (`[tool.blender] uses`)."""  # ty: ignore[blender-invalid-addon-metadata]
# The manifest also declares `regchk_uses_missing`, which no module provides: reported on the line above. Where both
# add-ons register a name (`Scene.regchk_uses_shared`), the add-on's own registration comes first.

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
    bpy.types.Scene.regchk_uses_shared = StringProperty()


def unregister():
    del bpy.types.Scene.regchk_uses_shared
    del bpy.types.Object.regchk_uses_label
    bpy.utils.unregister_class(REGCHK_USES_OT_run)
