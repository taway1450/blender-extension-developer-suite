"""@persistent returns the function unchanged; handlers have the arguments Blender passes at runtime."""

from __future__ import annotations

from collections.abc import Callable
from typing import assert_type

import bpy
from bpy.app.handlers import persistent

from . import on_load_post, tick


def persistent_keeps_the_function() -> None:
    on_load_post("file.blend", None)
    on_load_post(1)  # ty: ignore[missing-argument]


@persistent
def typed_handler(filepath: str, unused: None) -> None:
    pass


def one_argument(filepath: str) -> None:
    pass


def no_arguments() -> None:
    pass


def handler_signatures() -> None:
    handler: Callable[[str, None], None] = typed_handler
    bpy.app.handlers.load_post.append(typed_handler)
    # Blender passes a handler that takes one parameter only the file path, and any other handler two arguments.
    bpy.app.handlers.load_post.append(one_argument)
    bpy.app.handlers.load_post.append(no_arguments)  # ty: ignore[invalid-argument-type]  # bare-ok: the stubs already reject a handler without parameters; the checker must keep it so


def timers() -> None:
    bpy.app.timers.register(tick)
