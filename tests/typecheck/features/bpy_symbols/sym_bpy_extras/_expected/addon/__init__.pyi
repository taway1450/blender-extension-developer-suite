"""Reference stub of sym_bpy_extras."""

from typing import Literal

from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper

class SYM_BPY_EXTRAS_OT_import(Operator, ImportHelper):
    filter_glob: str
    axis_forward: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
    axis_up: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]

class SYM_BPY_EXTRAS_OT_export(Operator, ExportHelper): ...

class SYM_BPY_EXTRAS_OT_export_module(Operator, ExportHelper):
    axis_forward: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
    axis_up: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]

def register() -> None: ...
def unregister() -> None: ...
