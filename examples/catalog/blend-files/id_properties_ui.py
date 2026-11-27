# /// catalog
# title = "`id_properties_ui`"
# section = "custom-properties"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs have no `idprop.types.IDPropertyUIManager`, and type an `Object` key as an `int`."
# "fake-bpy-module/5.2" = "These stubs have no `idprop.types.IDPropertyUIManager` and type `id_properties_ui` as returning `None`."
# ///
"""`obj.id_properties_ui("key")` gives the settings Blender shows for a custom property: its range, its step, its
description. The stubs type it as an `IDPropertyUIManager`, so its methods are checked."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Object
from idprop.types import IDPropertyUIManager


def example(ob: Object) -> None:
    ob["scatter_seed"] = 7
    ui = ob.id_properties_ui("scatter_seed")
    assert_type(ui, IDPropertyUIManager)
    ui.update(min=0, max=100, description="The seed of the scatter")
    ui.updte(min=0)  # ty: ignore[missing-attribute]
