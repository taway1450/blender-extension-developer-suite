"""Enum items: the item names and descriptions should be visible somewhere (check:ide; never imported)."""

from __future__ import annotations

from bpy.types import Object, Operator


def enum_property(obj: Object) -> None:
    obj.type
    #   ^hover
    obj.type == "MESH"
    #            ^hover-contains "Mesh"


def operator_return(op: Operator) -> set[str]:
    op.report({"WARNING"}, "x")
    #           ^hover-contains "Warning"
    return {"FINISHED"}
    #        ^hover-contains "Finished"
