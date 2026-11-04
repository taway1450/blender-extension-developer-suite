"""Reference stub: bpy.ops.regchk_unregistered as the checker synthesises it."""

from typing import Literal

def used(execution_context: str = ..., undo: bool = ..., /, *, steps: int = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]: ...
