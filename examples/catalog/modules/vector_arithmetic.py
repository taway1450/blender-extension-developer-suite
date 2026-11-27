# /// catalog
# title = "`Vector` arithmetic"
# section = "math-mesh"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["bpy_symbols"]
# ///
"""`mathutils` types work with Python's operators: a `Vector` times a number is a `Vector`, a `Matrix` times a `Vector`
with `@` is a `Vector`. The stubs declare each operator with its types, so a result keeps its type and an operation the
types do not support is reported."""

# catalog: hide
from typing import assert_type

# catalog: show
from mathutils import Matrix, Vector


def example(offset: Vector, transform: Matrix) -> None:
    assert_type(offset * 2.0, Vector)
    assert_type(transform @ offset, Vector)
    print(offset + "up")  # ty: ignore[unsupported-operator]
