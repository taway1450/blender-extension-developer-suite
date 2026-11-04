"""Feature test: annotations whose value is a property made somewhere else. Blender evaluates the annotation and
only needs a deferred property as its value, so anything that evaluates to one works.

The checker evaluates the annotation as a value: when it can tell which bpy.props function made the value and with
which options, the field has that property's type. See README.md for what is expected when it cannot.
"""

import functools

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

# Values and aliases.
COMMON = IntProperty(name="Common", min=0)
Float = FloatProperty
ColorProperty = functools.partial(FloatVectorProperty, subtype="COLOR", size=3)
PROPS = {"weight": FloatProperty(), "label": StringProperty()}
PAIR = (IntProperty(), BoolProperty())
USE_FLOAT = bpy.app.version >= (4, 0, 0)
SETTINGS = dict(subtype="TRANSLATION", size=3)


# Wrapper functions.
def color_property():
    return FloatVectorProperty(subtype="COLOR")


def translation(size):
    return FloatVectorProperty(subtype="TRANSLATION", size=size)


def vector(**kwargs):
    return FloatVectorProperty(**kwargs)


def enum_of(items):
    return EnumProperty(items=items)


def float_or_int(use_float):
    if use_float:
        return FloatProperty()
    return IntProperty()


class WRAP_VALUES_Settings(PropertyGroup):
    # Exact: the value is a known property call.
    common_a: COMMON
    common_b: COMMON  # the same deferred property for two fields
    alias: Float(default=1.0)
    partial_color: ColorProperty()
    partial_override: ColorProperty(size=4)  # a keyword of the call replaces the partial's: a 4-float array
    from_dict: PROPS["weight"]
    from_dict_str: PROPS["label"]
    from_tuple: PAIR[0]
    from_tuple_bool: PAIR[1]
    # Exact by evaluating small wrappers at the call (a single return of a property call).
    wrapped: color_property()
    wrapped_size: translation(2)
    wrapped_kwargs: vector(subtype="COLOR")
    wrapped_enum: enum_of([("A", "A", ""), ("B", "B", "")])
    # The kind is known, an option that decides the type is not.
    either: float_or_int(USE_FLOAT)  # one of the returns: float | int
    unknown_options: FloatVectorProperty(**SETTINGS)  # FloatVector with unknown subtype and size: Any
    scalar_unknown_options: IntProperty(**{"min": 0})  # no option changes an int: int
    # Nothing is known: Any, and no error.
    opaque: getattr(bpy.props, "".join(["Int", "Property"]))()


def register():
    bpy.utils.register_class(WRAP_VALUES_Settings)


def unregister():
    bpy.utils.unregister_class(WRAP_VALUES_Settings)
