"""Callers see the overrides with the parent's parameter and return types."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

from bpy.types import Context, Event, Header, Menu, Operator, Panel, UILayout

from . import INH_OVERRIDES_MT_menu, INH_OVERRIDES_Node, INH_OVERRIDES_OT_all, INH_OVERRIDES_OT_variants, INH_OVERRIDES_UL_short

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def operator(op: INH_OVERRIDES_OT_all, context: Context, event: Event) -> None:
    assert_type(op.execute(context), Result)
    assert_type(op.invoke(context, event), Result)
    assert_type(op.modal(context, event), Result)
    assert_type(op.check(context), bool)
    assert_type(INH_OVERRIDES_OT_all.poll(context), bool)
    assert_type(INH_OVERRIDES_OT_all.description(context, op.properties), str | None)
    op.execute(1)  # ty: ignore[invalid-argument-type]
    op.invoke(context, context)  # ty: ignore[invalid-argument-type]


def variants(op: INH_OVERRIDES_OT_variants, context: Context, event: Event) -> None:
    assert_type(op.execute(context), Result)
    assert_type(op.execute(ctx=context), Result)
    assert_type(op.check(context, verbose=True), bool)
    op.check(context, verbose="yes")  # ty: ignore[invalid-argument-type]
    op.modal(context, event, 1, 2)


def ui(menu: INH_OVERRIDES_MT_menu, ui_list: INH_OVERRIDES_UL_short, context: Context, layout: UILayout) -> None:
    assert_type(menu.draw(context), None)
    ui_list.draw_item(context, layout, None, None, 0, None)


def node(node: INH_OVERRIDES_Node, context: Context, layout: UILayout) -> None:
    assert_type(node.draw_label(), str)
    node.draw_buttons(context, layout)
    node.draw_buttons(context, 1)  # ty: ignore[invalid-argument-type]


OTHER_PANELS: list[Panel] = []


class CheckLayoutPanel(Panel):  # ty: ignore[blender-unregistered-class]
    def draw(this, context):  # the first parameter, whatever its name, is the panel being drawn
        assert_type(this.layout, UILayout)  # oracle-skip: a class defined in the check file
        layout = this.layout
        assert_type(layout, UILayout)  # oracle-skip: a class defined in the check file
        for other in OTHER_PANELS:
            assert_type(other.layout, UILayout | None)  # bare-ok: another panel is not being drawn, so its layout may be None

    def draw_settings(self, context: Context) -> None:  # a helper the panel's draw calls on itself
        assert_type(self.layout, UILayout)  # oracle-skip: a class defined in the check file


class INH_OVERRIDES_MT_check_layout(Menu):  # ty: ignore[blender-unregistered-class]
    bl_label = "Check layout"

    def draw(self, context):
        self.draw_items()

    def draw_items(self) -> None:
        assert_type(self.layout, UILayout)  # oracle-skip: a class defined in the check file


class INH_OVERRIDES_HT_check_layout(Header):  # ty: ignore[blender-unregistered-class]
    bl_space_type = "VIEW_3D"

    def draw(self, context):
        self._draw_mode(context)

    def _draw_mode(self, context: Context) -> None:
        assert_type(self.layout, UILayout)  # oracle-skip: a class defined in the check file


class INH_OVERRIDES_OT_check_layout(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "inh_overrides.check_layout"
    bl_label = "Check layout"

    def draw(self, context):
        self._draw_config()

    def _draw_config(self) -> None:
        assert_type(self.layout, UILayout | None)  # bare-ok: an Operator's helper may run outside draw, where its layout is None
