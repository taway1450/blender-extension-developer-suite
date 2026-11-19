"""Feature test: a test case's assertion stops the test when it fails, as an assert statement does, so the code after
`self.assertIsNotNone(x)` reads `x` as not None, and after `self.assertTrue(x)` as truthy. Blender's tests read the
data they just loaded or made this way. The narrowing holds for the rest of the block, as after an assert statement.
The TestCase is never run: the assert_type calls are checked statically."""

import unittest
from typing import assert_type

import bpy
from bpy.types import Object


class NarrowAssertionsTest(unittest.TestCase):
    def test_is_not_none(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertIsNotNone(ob)
        assert_type(ob, Object)
        self.assertEqual(ob.name, "Cube")

    def test_true(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertTrue(ob)
        assert_type(ob.name, str)  # `ob` is a truthy Object, as after `assert ob`

    def test_attribute(self) -> None:
        ob = bpy.data.objects["Cube"]
        self.assertIsNotNone(ob.animation_data)
        assert_type(ob.animation_data, bpy.types.AnimData)

    def test_message(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertIsNotNone(ob, "the test file has a cube")
        assert_type(ob, Object)

    def test_other_receiver(self) -> None:
        other = unittest.TestCase()
        ob = bpy.data.objects.get("Cube")
        other.assertIsNotNone(ob)
        assert_type(ob, Object | None)  # bare-ok: another test case's assertion is not this test's

    def test_not_a_statement(self) -> None:
        ob = bpy.data.objects.get("Cube")
        checks = [self.assertIsNotNone(ob)]
        assert_type(ob, Object | None)  # bare-ok: only an assertion statement narrows
        del checks


class NotATestCase:
    """A class with its own `assertIsNotNone`: nothing says it stops when the value is None."""

    def assertIsNotNone(self, value: object) -> None:
        print(value)

    def check(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertIsNotNone(ob)
        assert_type(ob, Object | None)  # bare-ok: not a TestCase, its assertion may return


class BaseTest(unittest.TestCase):
    """An intermediate base: its subclasses are test cases too."""


class DerivedTest(BaseTest):
    def test_is_not_none(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertIsNotNone(ob)
        assert_type(ob, Object)  # a TestCase through BaseTest


class AsyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_is_not_none(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertIsNotNone(ob)
        assert_type(ob, Object)  # IsolatedAsyncioTestCase is a TestCase


class AssertionMixin:
    """A mixin mixed into test cases: its `self` may be any class, so its assertion does not narrow."""

    def check_cube(self) -> None:
        ob = bpy.data.objects.get("Cube")
        self.assertIsNotNone(ob)  # ty: ignore[missing-attribute]  # bare-ok: a mixin has no assertIsNotNone
        assert_type(ob, Object | None)  # bare-ok: `self` is not known to be a TestCase


def register():
    pass


def unregister():
    pass
