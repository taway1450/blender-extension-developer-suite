"""Feature test: an add-on whose properties regchk_uses reads, as Cycles' `scene.cycles` is read by other add-ons."""

import bpy
from bpy.props import IntProperty, PointerProperty
from bpy.types import PropertyGroup


class REGCHK_USES_PROVIDER_Settings(PropertyGroup):
    samples: IntProperty()


def register():
    bpy.utils.register_class(REGCHK_USES_PROVIDER_Settings)
    bpy.types.Scene.regchk_uses_provider = PointerProperty(type=REGCHK_USES_PROVIDER_Settings)
    bpy.types.Object.regchk_uses_provider_count = IntProperty()
    bpy.types.Scene.regchk_uses_shared = IntProperty()


def unregister():
    del bpy.types.Scene.regchk_uses_shared
    del bpy.types.Object.regchk_uses_provider_count
    del bpy.types.Scene.regchk_uses_provider
    bpy.utils.unregister_class(REGCHK_USES_PROVIDER_Settings)
