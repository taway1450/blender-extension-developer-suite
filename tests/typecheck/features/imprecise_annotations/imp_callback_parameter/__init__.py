"""Feature test: callback parameters annotated with the subclass Blender passes.

Blender calls `UIList.draw_item` with the `data` and `item` the add-on gave `template_list`, so annotating them with
that subclass (`data: Armature`, `item: MyItem`) is narrower than the parent's `bpy_struct` but right: it is
accepted and reported (blender-imprecise-callback-parameter), and the body sees the annotated type. A type that is
no subtype of the parent's stays ty's invalid-method-override."""

import bpy
from bpy.props import StringProperty
from bpy.types import Armature, Context, PropertyGroup, UILayout, UIList


class ImpCallbackParameterItem(PropertyGroup):
    label: StringProperty()


class IMP_CALLBACK_PARAMETER_UL_layers(UIList):
    def draw_item(self, context, layout, data: Armature, item, icon, active_data, active_property):  # ty: ignore[blender-imprecise-callback-parameter]
        print(data.name)


class IMP_CALLBACK_PARAMETER_UL_items(UIList):
    def draw_item(self, context: Context, layout: UILayout, data, item: ImpCallbackParameterItem, icon, active_data, active_property):  # ty: ignore[blender-imprecise-callback-parameter]
        layout.label(text=item.label)


class IMP_CALLBACK_PARAMETER_UL_unrelated(UIList):
    def draw_item(self, context, layout, data, item, icon: str, active_data, active_property):  # ty: ignore[invalid-method-override]  # bare-ok: a type that is no subtype of the parent's stays an error
        pass


classes = (
    ImpCallbackParameterItem,
    IMP_CALLBACK_PARAMETER_UL_layers,
    IMP_CALLBACK_PARAMETER_UL_items,
    IMP_CALLBACK_PARAMETER_UL_unrelated,
)
register, unregister = bpy.utils.register_classes_factory(classes)
