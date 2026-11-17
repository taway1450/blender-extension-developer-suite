"""Feature test: ``bl_rna.properties["name"]``, the RNA property behind an attribute, is the ``Property`` subclass of
its kind (``rna_Property_refine``), for Blender's structs and for an add-on's own properties."""

import bpy
from bpy.props import EnumProperty, IntProperty
from bpy.types import PropertyGroup


class PROPS_RNA_Settings(PropertyGroup):
    count: IntProperty()
    flags: EnumProperty(items=[("A", "A", ""), ("B", "B", "")], options={"ENUM_FLAG"})


def register():
    bpy.utils.register_class(PROPS_RNA_Settings)


def unregister():
    bpy.utils.unregister_class(PROPS_RNA_Settings)
