"""Not an add-on (no manifest, no bl_info): a script Blender runs, such as a performance test. A property annotation
whose function is a parameter cannot be evaluated, but Blender still evaluates it: the member is a property of any
type, with no error, as in an add-on."""

import bpy


def make_group(property_function):
    class WRAP_SCRIPT_Group(bpy.types.PropertyGroup):
        value: property_function()

    return WRAP_SCRIPT_Group
