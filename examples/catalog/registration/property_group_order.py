# /// catalog
# title = "A PropertyGroup registered after the class pointing to it"
# section = "order"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
#
# [evidence]
# addon = "registration_checks/regchk_order"
# register = "fails"
# says = "PropertyGroup registered after the class that points to it"
# ///
"""A `PointerProperty` or `CollectionProperty` needs its PropertyGroup registered first: Blender raises `ValueError`
for a class whose property points to an unregistered one. The checker follows the order of `register()` and reports
the early registration. Unregistering in another order works, so it is not reported."""

import bpy
from bpy.props import PointerProperty
from bpy.types import PropertyGroup

bl_info = {
    "name": "Catalog: a PropertyGroup registered after the class pointing to it",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class PROPERTY_GROUP_ORDER_Leaf(PropertyGroup):
    pass


class PROPERTY_GROUP_ORDER_Tree(PropertyGroup):
    leaf: PointerProperty(type=PROPERTY_GROUP_ORDER_Leaf)


classes = (
    PROPERTY_GROUP_ORDER_Tree,  # ty: ignore[blender-register-order]
    PROPERTY_GROUP_ORDER_Leaf,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
