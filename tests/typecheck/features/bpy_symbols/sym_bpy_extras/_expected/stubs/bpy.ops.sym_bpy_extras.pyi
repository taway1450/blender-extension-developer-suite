"""Reference stub: bpy.ops.sym_bpy_extras, with the mixins' properties as keyword arguments."""

from typing import Literal

def import_file(execution_context: str = ..., undo: bool = ..., /, *, filepath: str = ..., filter_glob: str = ...,
                axis_forward: Literal["X", "Y", "Z", "-X", "-Y", "-Z"] = ..., axis_up: Literal["X", "Y", "Z", "-X", "-Y", "-Z"] = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]: ...
def export_file(execution_context: str = ..., undo: bool = ..., /, *, filepath: str = ...,
                check_existing: bool = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]: ...
def export_module(execution_context: str = ..., undo: bool = ..., /, *, filepath: str = ...,
                  check_existing: bool = ..., axis_forward: Literal["X", "Y", "Z", "-X", "-Y", "-Z"] = ..., axis_up: Literal["X", "Y", "Z", "-X", "-Y", "-Z"] = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]: ...
