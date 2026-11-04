"""Annotations from base classes and mixins (classes that are not bpy_struct subclasses) are properties too."""

from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup


class CountMixin:
    count: IntProperty()


class LabelMixin:
    label: StringProperty()


class PROPS_STYLES_Base(PropertyGroup):
    base_value: IntProperty()


class PROPS_STYLES_Child(PROPS_STYLES_Base):
    child_value: FloatProperty()


class PROPS_STYLES_Override(PROPS_STYLES_Base):
    base_value: StringProperty()  # replaces the base class's property


class PROPS_STYLES_MixinFirst(CountMixin, LabelMixin, PropertyGroup):
    own: FloatProperty()


class PROPS_STYLES_MixinLast(PropertyGroup, CountMixin):
    pass


classes = (PROPS_STYLES_Base, PROPS_STYLES_Child, PROPS_STYLES_Override, PROPS_STYLES_MixinFirst,
           PROPS_STYLES_MixinLast)
