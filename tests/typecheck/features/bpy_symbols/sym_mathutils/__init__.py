"""Feature test: mathutils values as property defaults, with mathutils imported in different ways."""

import bpy
import mathutils
from bpy.props import FloatVectorProperty, PointerProperty
from bpy.types import PropertyGroup
from mathutils import Color
from mathutils import Euler as E
from mathutils import Matrix, Quaternion


class SYM_MATHUTILS_Settings(PropertyGroup):
    location: FloatVectorProperty(subtype="TRANSLATION", default=mathutils.Vector((0.0, 0.0, 1.0)))
    tint: FloatVectorProperty(subtype="COLOR", default=Color((1.0, 0.5, 0.0)), min=0.0, max=1.0)
    rotation: FloatVectorProperty(subtype="EULER", default=E((0.0, 0.0, 0.5)))
    orientation: FloatVectorProperty(subtype="QUATERNION", size=4, default=Quaternion((1.0, 0.0, 0.0, 0.0)))
    transform: FloatVectorProperty(subtype="MATRIX", size=(4, 4), default=Matrix.Identity(4))


def register():
    bpy.utils.register_class(SYM_MATHUTILS_Settings)
    bpy.types.Scene.sym_mathutils = PointerProperty(type=SYM_MATHUTILS_Settings)


def unregister():
    del bpy.types.Scene.sym_mathutils
    bpy.utils.unregister_class(SYM_MATHUTILS_Settings)
