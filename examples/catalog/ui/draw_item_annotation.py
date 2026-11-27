# /// catalog
# title = "An annotated `draw_item`"
# section = "lists"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["imprecise_annotations"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `draw_item`'s parameters as `AnyType`, which the annotation does not narrow, so the override is reported; `layout` is `UILayout | None` there."
# "fake-bpy-module/5.2" = "These stubs type `draw_item`'s `layout` as `UILayout | None`, so its read is reported."
# ///
"""An annotation of `draw_item`'s `item` with the type the list shows is accepted, and the body sees that type. The
stubs type `data` and `item` as `bpy_struct`, any Blender struct, and an override's parameter may not be narrower
than its parent's; but Blender passes what the add-on gave `template_list`, so it is right. Against the parent's
signature, which the stubs state precisely, the annotation is the less precise form, so the checker reports it as an
Imprecise annotation. Left unannotated, `item` is typed from `template_list` anyway."""

from bpy.props import StringProperty
from bpy.types import PropertyGroup, UIList


class Layer(PropertyGroup):
    label: StringProperty()


class LAYERS_UL_list(UIList):
    def draw_item(self, context, layout, data, item: Layer, icon, active_data, active_property):  # ty: ignore[blender-imprecise-callback-parameter]
        layout.label(text=item.label)
