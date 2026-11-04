"""Reference stub of opcall_macro."""

from bpy.types import Macro, Operator

class OPCALL_MACRO_OT_step(Operator):
    amount: int

class OPCALL_MACRO_OT_label(Operator):
    text: str

class OPCALL_MACRO_OT_combo(Macro): ...

def register() -> None: ...
def unregister() -> None: ...
