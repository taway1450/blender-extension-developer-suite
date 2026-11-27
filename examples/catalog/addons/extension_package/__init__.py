# /// catalog
# title = "A manifest makes the package an extension"
# section = "metadata"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["addon_discovery"]
# ///
"""The checker reads a package with a `blender_manifest.toml` as an extension, even with a `bl_info` left over from
before. Installed, the extension is the package `bl_ext.<repository>.<id>`, and the repository is only known then, so
`__package__` is typed `str` rather than the `str | None` of a plain module."""

# catalog: hide
from typing import assert_type

# catalog: show
bl_info = {
    "name": "Left over from before the manifest",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "category": "Development",
}


def example() -> None:
    assert_type(__package__, str)


def register():
    pass


def unregister():
    pass
