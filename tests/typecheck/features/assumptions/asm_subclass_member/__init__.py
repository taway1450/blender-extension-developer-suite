"""Feature test: a struct read by index or by name (`ob.constraints[0]`, `ob.modifiers["Subdivision"]`,
`bpy.data.lights["Key"]`, `node.inputs["Color"]`) is typed as its refined base, but Blender always hands it out as
the subclass its Type tag names. Code that reads a member only some of those subclasses declare relies on knowing
which one it holds. The checker types the read as the union of the subclasses' declarations and reports it under
blender-assumed-subclass-member. It does so only for refined bases with a Type tag: a member no subclass declares
(a misspelling), a member of `ID`'s subclasses read on an `ID` and one of `TextCurve` read on a `Curve` (no Type tag)
stay errors. The assert_type calls are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import ID, Curve, Node, Object


def first_target(ob: Object) -> Object | None:
    con = ob.constraints[0]
    assert_type(con.target, Object | None)  # ty: ignore[blender-assumed-subclass-member]
    return con.target  # ty: ignore[blender-assumed-subclass-member]


def subdivision_levels(ob: Object) -> int:
    md = ob.modifiers["Subdivision"]
    assert_type(md.levels, int)  # ty: ignore[blender-assumed-subclass-member]
    return md.levels  # ty: ignore[blender-assumed-subclass-member]


def key_spot_size() -> float:
    light = bpy.data.lights["Key"]
    assert_type(light.spot_size, float)  # ty: ignore[blender-assumed-subclass-member]
    return light.spot_size  # ty: ignore[blender-assumed-subclass-member]


def color_input(node: Node) -> None:
    print(node.inputs["Color"].default_value)  # ty: ignore[blender-assumed-subclass-member]


def tested_type(ob: Object) -> Object | None:
    con = ob.constraints[0]
    if con.type == 'COPY_LOCATION':
        return con.target  # narrowed by the Type tag: not reported
    return None


def misspelt(ob: Object) -> None:
    con = ob.constraints[0]
    print(con.targt)  # ty: ignore[missing-attribute]  # bare-ok: no subclass declares it, so it stays an error


def not_refined(data: ID, curve: Curve) -> None:
    print(data.vertices)  # ty: ignore[missing-attribute]  # bare-ok: `ID` is no refined base with a Type tag
    print(curve.body)  # ty: ignore[missing-attribute]  # bare-ok: `Curve` has no Type tag


def register():
    pass


def unregister():
    pass
