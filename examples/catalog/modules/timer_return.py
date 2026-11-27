# /// catalog
# title = "A timer's return value"
# section = "callbacks"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["bpy_symbols"]
# blender-docs = ["bpy.app.timers"]
# ///
"""A function given to `bpy.app.timers.register` returns the seconds until its next call, or `None` to stop. The stubs
type it as a function returning `float | None`, so a function that returns something else is reported."""

import bpy


def every_second() -> float | None:
    return 1.0


def wrong() -> str:
    return "1.0"


def register() -> None:
    bpy.app.timers.register(every_second)
    bpy.app.timers.register(wrong)  # ty: ignore[invalid-argument-type]
