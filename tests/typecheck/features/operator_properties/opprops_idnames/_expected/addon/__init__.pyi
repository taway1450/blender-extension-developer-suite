"""Reference stub of opprops_idnames."""

from typing import Literal

from bpy.types import Operator, Panel

STEP_IDNAME: Literal["opprops_idnames.step"]
CATEGORY: Literal["opprops_idnames"]

class OPPROPS_IDNAMES_OT_step(Operator):
    bl_idname: Literal["opprops_idnames.step"]
    factor: float

class OPPROPS_IDNAMES_OT_odd(Operator):
    bl_idname: Literal["opprops_idnames_ot_odd.run"]
    steps: float

class OPPROPS_IDNAMES_PT_panel(Panel): ...

classes: tuple[type[OPPROPS_IDNAMES_OT_step], type[OPPROPS_IDNAMES_OT_odd], type[OPPROPS_IDNAMES_PT_panel]]
def register() -> None: ...
def unregister() -> None: ...
