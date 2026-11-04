"""ImportHelper declares filepath, ExportHelper filepath and check_existing, orientation_helper adds
axis_forward and axis_up (enums of the six axes). The stubs leave these properties out."""

from __future__ import annotations

from typing import Literal, assert_type

import bpy

from . import SYM_BPY_EXTRAS_OT_export, SYM_BPY_EXTRAS_OT_export_module, SYM_BPY_EXTRAS_OT_import


def mixin_properties(imp: SYM_BPY_EXTRAS_OT_import, exp: SYM_BPY_EXTRAS_OT_export,
                     mod: SYM_BPY_EXTRAS_OT_export_module) -> None:
    assert_type(imp.filepath, str)
    assert_type(imp.filter_glob, str)
    assert_type(imp.axis_forward, Literal["X", "Y", "Z", "-X", "-Y", "-Z"])
    assert_type(imp.axis_up, Literal["X", "Y", "Z", "-X", "-Y", "-Z"])
    assert_type(exp.filepath, str)
    assert_type(exp.check_existing, bool)
    assert_type(mod.filepath, str)
    assert_type(mod.axis_up, Literal["X", "Y", "Z", "-X", "-Y", "-Z"])
    imp.axis_up = "W"  # ty: ignore[invalid-assignment]


def calls() -> None:
    assert_type(bpy.ops.sym_bpy_extras.import_file(filepath="a.txt", axis_up="Z"), set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]])
    bpy.ops.sym_bpy_extras.import_file(axis_up="W")  # ty: ignore[invalid-argument-type]
    bpy.ops.sym_bpy_extras.export_file(filepath="a.txt", check_existing=False)
