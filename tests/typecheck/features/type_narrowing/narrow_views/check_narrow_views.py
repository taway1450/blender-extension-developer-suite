"""What a Type tag test does not narrow: the data read into a variable before the test is another binding."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Mesh, Object


def data_before_test(ob: Object) -> None:
    data = ob.data
    if ob.type == 'MESH':
        assert_type(data, Mesh)  # ty: ignore[type-assertion-failure]  # bare-ok: `data` was read before the test
        assert_type(ob.data, Mesh)  # oracle-skip: narrowing by a Type tag needs the checker
