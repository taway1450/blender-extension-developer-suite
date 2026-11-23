"""The addon sees the registrations of the add-on it declares, and its own."""

from typing import assert_type

from bpy.types import Object, Scene

from regchk_uses_provider import REGCHK_USES_PROVIDER_Settings


def declared(scene: Scene, ob: Object) -> None:
    assert_type(scene.regchk_uses_provider, REGCHK_USES_PROVIDER_Settings)
    assert_type(scene.regchk_uses_provider.samples, int)
    assert_type(ob.regchk_uses_provider_count, int)
    assert_type(ob.regchk_uses_label, str)


def own_first(scene: Scene) -> None:
    # regchk_uses_provider registers it as an IntProperty: the add-on's own StringProperty wins.
    assert_type(scene.regchk_uses_shared, str)


def undeclared(scene: Scene) -> None:
    scene.regchk_isolation_a_value  # ty: ignore[missing-attribute]  # bare-ok: must stay missing: not declared
