"""A stub the add-on ships for its users' type checkers, with no module behind it. Blender never loads a .pyi file,
so the property rules do not apply here: neither the old form nor an annotation on a Panel is reported."""

from bpy.props import IntProperty
from bpy.types import Panel, PropertyGroup

class PROPS_STYLES_StubGroup(PropertyGroup):
    value = IntProperty()

class PROPS_STYLES_PT_stub(Panel):
    value: IntProperty()
