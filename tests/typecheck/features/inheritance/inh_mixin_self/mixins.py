"""Mixins whose users are in another module of the add-on (__init__.py). A mixin has no bpy.types class in its MRO,
so Python alone types self in its methods as the bare mixin. In Blender self is always one of its users, so ty
types it as the mixin and the bpy.types classes of the users, silently: PanelMixin's self is a Panel too. Only
members that every user's Blender class has resolve, so a Panel mixin calling report (an Operator method) stays an
error. A mixin method is a draw callback (self.layout is never None) when it is one for every user.

A mixin whose users all derive from unittest.TestCase is typed the same way: its self is a TestCase too, so the test
case's assertions resolve and narrow.

A mixin that no class of the add-on uses keeps its bare type: its users may be in another add-on, or made at
runtime."""

from typing import assert_type

import bpy
from bpy.types import Object, UILayout


class PanelMixin:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw_common(self, context):
        layout = self.layout
        assert_type(layout, UILayout)
        assert_type(self.bl_label, str)
        layout.label(text=self.bl_label)

    def notify(self):
        self.report({"INFO"}, "drawn")  # ty: ignore[missing-attribute]  # bare-ok: a Panel has no report, still an error


class OperatorMixin:
    def finish(self, context):
        assert_type(self.report({"INFO"}, "done"), None)
        assert_type(self.layout, UILayout | None)
        return {"FINISHED"}


class DrawnMixin:
    """Used by a Panel and a Menu: every user draws it, so self.layout is set."""

    def draw_title(self, context):
        assert_type(self.layout, UILayout)
        self.layout.label(text=self.bl_label)


class SharedMixin:
    """Used by a Panel and an Operator: an Operator helper may run outside draw, where its layout is None."""

    def draw_title(self, context):
        assert_type(self.layout, UILayout | None)


class UnusedMixin:
    def draw_common(self, context):
        self.layout.label(text="unused")  # ty: ignore[missing-attribute]  # bare-ok: no user, self stays the bare mixin


class TestCaseMixin:
    """Used by two unittest.TestCase subclasses: self is a TestCase too."""

    def check_cube(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertIsNotNone(ob)
        assert_type(ob, Object)
        self.assertEqual(ob.name, "Cube")
