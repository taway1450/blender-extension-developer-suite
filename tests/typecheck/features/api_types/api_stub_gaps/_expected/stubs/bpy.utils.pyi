"""Reference stub delta: public functions of bpy.utils that are not in its __all__, and keyconfig_set returns whether
it loaded the key configuration."""

from collections.abc import Callable
from typing import Literal

def system_resource(type: str, *, path: str | bytes = "") -> str: ...
def is_path_builtin(path: str) -> bool: ...
def keyconfig_set(
    filepath: str,
    *,
    report: Callable[
        [
            set[
                Literal[
                    "DEBUG",
                    "INFO",
                    "OPERATOR",
                    "PROPERTY",
                    "WARNING",
                    "ERROR",
                    "ERROR_INVALID_INPUT",
                    "ERROR_INVALID_CONTEXT",
                    "ERROR_OUT_OF_MEMORY",
                ]
            ],
            str,
        ],
        None,
    ]
    | None = None,
) -> bool: ...
