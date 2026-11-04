"""__package__ in a sub-package of an extension (bl_ext.<repository>.<id>.sub)."""

from __future__ import annotations

from typing import assert_type


def package() -> None:
    assert_type(__package__, str)  # oracle-skip: stock ty types __package__ as str | None
