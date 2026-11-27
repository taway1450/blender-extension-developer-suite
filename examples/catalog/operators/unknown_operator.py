# /// catalog
# title = "An idname no operator has"
# section = "idnames"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_properties"]
# ///
"""An idname no operator has, given to `layout.operator`, a key map item or a tool's key map, is reported inside an
add-on. There the checker knows Blender's operators and the add-on's own, and reports any other idname; in a file
outside an add-on it reports nothing, since the operator may be registered elsewhere."""

from bpy.types import UILayout

bl_info = {
    "name": "Catalog: an idname no operator has",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


def draw_buttons(layout: UILayout) -> None:
    layout.operator("object.select_all")
    layout.operator("object.select_al")  # ty: ignore[blender-unknown-operator]


def register():
    pass


def unregister():
    pass
