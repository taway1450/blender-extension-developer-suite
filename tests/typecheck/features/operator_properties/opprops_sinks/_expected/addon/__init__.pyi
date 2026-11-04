"""Reference stub of opprops_sinks."""

from typing import Literal

from bpy.types import Macro, Operator, Panel, _opprops_sinks_bare_properties, _opprops_sinks_step_properties

class OPPROPS_SINKS_OT_step(Operator):
    amount: int
    mode: Literal["A", "B"]
    label: str
    flags: set[Literal["A", "B"]]
    @property
    def properties(self) -> _opprops_sinks_step_properties: ...

class OPPROPS_SINKS_OT_bare(Operator):
    @property
    def properties(self) -> _opprops_sinks_bare_properties: ...

class OPPROPS_SINKS_OT_combo(Macro): ...
class OPPROPS_SINKS_PT_panel(Panel): ...

def register() -> None: ...
def unregister() -> None: ...
