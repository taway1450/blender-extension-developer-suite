"""Feature test: a class or a Registered property that register() registers only on a branch (a Blender version
check, an except handler, a module-level list extended under a condition, a timer) may be registered, so the checker
takes it as registered, and reports each use of it (`bpy.ops.x.y`, a Registered property read, `.preferences`) under
blender-assumed-registration. What register() always registers is not reported. The uses run in callbacks only."""

import bpy
from bpy.props import BoolProperty, IntProperty
from bpy.types import AddonPreferences, Operator, Panel


class ASM_REGISTRATION_OT_always(Operator):
    bl_idname = "asm_registration.always"
    bl_label = "Always"

    def execute(self, context):
        return {"FINISHED"}


class ASM_REGISTRATION_OT_version(Operator):
    bl_idname = "asm_registration.version"
    bl_label = "Version"

    def execute(self, context):
        return {"FINISHED"}


class ASM_REGISTRATION_OT_primary(Operator):
    bl_idname = "asm_registration.primary"
    bl_label = "Primary"

    def execute(self, context):
        return {"FINISHED"}


class ASM_REGISTRATION_OT_fallback(Operator):
    bl_idname = "asm_registration.fallback"
    bl_label = "Fallback"

    def execute(self, context):
        return {"FINISHED"}


class ASM_REGISTRATION_OT_listed(Operator):
    bl_idname = "asm_registration.listed"
    bl_label = "Listed"

    def execute(self, context):
        return {"FINISHED"}


class ASM_REGISTRATION_OT_later(Operator):
    bl_idname = "asm_registration.later"
    bl_label = "Later"

    def execute(self, context):
        return {"FINISHED"}


class ASM_REGISTRATION_Preferences(AddonPreferences):
    bl_idname = __package__

    flag: BoolProperty()


class ASM_REGISTRATION_PT_panel(Panel):
    bl_label = "Assumed registration"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        layout.label(text=str(context.scene.asm_registration_always))
        layout.label(text=str(context.scene.asm_registration_new))  # ty: ignore[blender-assumed-registration]
        prefs = context.preferences.addons[__package__].preferences  # ty: ignore[blender-assumed-registration]
        layout.prop(prefs, "flag")


class ASM_REGISTRATION_OT_run(Operator):
    bl_idname = "asm_registration.run"
    bl_label = "Run"

    def execute(self, context):
        bpy.ops.asm_registration.always()
        bpy.ops.asm_registration.primary()
        bpy.ops.asm_registration.version()  # ty: ignore[blender-assumed-registration]
        bpy.ops.asm_registration.fallback()  # ty: ignore[blender-assumed-registration]
        bpy.ops.asm_registration.listed()  # ty: ignore[blender-assumed-registration]
        bpy.ops.asm_registration.later()  # ty: ignore[blender-assumed-registration]
        return {"FINISHED"}


extra = []
if bpy.app.version >= (4, 2, 0):
    extra.append(ASM_REGISTRATION_OT_listed)


def register_later():
    bpy.utils.register_class(ASM_REGISTRATION_OT_later)


def register():
    bpy.utils.register_class(ASM_REGISTRATION_OT_always)
    bpy.utils.register_class(ASM_REGISTRATION_PT_panel)
    bpy.utils.register_class(ASM_REGISTRATION_OT_run)
    bpy.types.Scene.asm_registration_always = IntProperty()
    if bpy.app.version >= (4, 2, 0):
        bpy.utils.register_class(ASM_REGISTRATION_OT_version)
        bpy.utils.register_class(ASM_REGISTRATION_Preferences)
        bpy.types.Scene.asm_registration_new = BoolProperty()
    try:
        bpy.utils.register_class(ASM_REGISTRATION_OT_primary)
    except ValueError:
        bpy.utils.register_class(ASM_REGISTRATION_OT_fallback)
    for cls in extra:
        bpy.utils.register_class(cls)
    bpy.app.timers.register(register_later, first_interval=0.0)


def unregister():
    for cls in (ASM_REGISTRATION_OT_later, *extra, ASM_REGISTRATION_OT_fallback, ASM_REGISTRATION_OT_primary,
                ASM_REGISTRATION_OT_version):
        if cls.is_registered:
            bpy.utils.unregister_class(cls)
    try:
        bpy.utils.unregister_class(ASM_REGISTRATION_Preferences)
    except RuntimeError:
        pass
    if hasattr(bpy.types.Scene, "asm_registration_new"):
        del bpy.types.Scene.asm_registration_new
    del bpy.types.Scene.asm_registration_always
    bpy.utils.unregister_class(ASM_REGISTRATION_OT_run)
    bpy.utils.unregister_class(ASM_REGISTRATION_PT_panel)
    bpy.utils.unregister_class(ASM_REGISTRATION_OT_always)
