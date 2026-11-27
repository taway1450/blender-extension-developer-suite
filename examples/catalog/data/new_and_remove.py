# /// catalog
# title = "`new()` and `remove()`"
# section = "collections"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["type_narrowing"]
#
# [differs]
# "fake-bpy-module/main" = "The checker narrows by the `rna_enum_*` alias a constructor's kind parameter shares with the Type tag; fake-bpy-module has no such alias, so the result stays the base type."
# "builtin/5.2" = "The checker narrows by the `rna_enum_*` alias a constructor's kind parameter shares with the Type tag; Blender 5.2's builtin stubs have no such alias, so the result stays the base type."
# "fake-bpy-module/5.2" = "The checker narrows by the `rna_enum_*` alias a constructor's kind parameter shares with the Type tag; these stubs have no such alias, so the result stays the base type."
# ///
"""`new()` creates an element of a collection and returns it; `remove()` deletes one, and takes only an element of that
collection's type. Where the kind of element is an
argument, as for a constraint or a light, the checker types the result as that kind: `constraints.new("COPY_LOCATION")`
is a `CopyLocationConstraint`."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import CopyLocationConstraint, Object, SpotLight


def example(ob: Object) -> None:
    constraint = ob.constraints.new("COPY_LOCATION")
    assert_type(constraint, CopyLocationConstraint)
    assert_type(bpy.data.lights.new("Key", "SPOT"), SpotLight)
    ob.constraints.remove(constraint)
    ob.constraints.remove(ob)  # ty: ignore[invalid-argument-type]
