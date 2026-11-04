"""Expected types and rejected mistakes when drawing panels."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Object, OperatorProperties, Panel, UILayout


def layout_types(panel: Panel, obj: Object) -> None:
    assert_type(panel.layout, UILayout)  # never None inside draw()
    layout = panel.layout
    assert_type(layout.row(), UILayout)
    assert_type(layout.column(align=True), UILayout)
    assert_type(layout.box(), UILayout)
    assert_type(layout.split(factor=0.5), UILayout)
    assert_type(layout.operator("object.select_all"), OperatorProperties)
    assert_type(layout.use_property_split, bool)


def rejected_calls(panel: Panel, obj: Object) -> None:
    layout = panel.layout
    layout.label(text="ok", icon="INFO")
    layout.label(text="bad icon", icon="NOT_AN_ICON")  # ty: ignore[invalid-argument-type]
    layout.prop(obj, "name", txt="typo")  # ty: ignore[unknown-argument]
    layout.row(align="yes")  # ty: ignore[invalid-argument-type]
