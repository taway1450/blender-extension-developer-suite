# /// catalog
# title = "Data a shipped file holds"
# section = "by-name"
# status = "not-handled"
# features = ["api_types"]
# later = "blend-file-typing"
# blender-docs = ["bpy.types.BlendDataLibraries"]
#
# [future]
# class = "planned"
# note = "Read the `.blend` files the add-on ships, so the names it loads and what they give are typed."
# tracked = "later/blend-file-typing"
#
# [differs]
# "fake-bpy-module/main" = "fake-bpy-module types `libraries.load` as returning `None`, so the `with` is reported too."
# "builtin/5.2" = "Blender 5.2's builtin stubs type `libraries.load` as returning `None`, so the `with` is reported too."
# "fake-bpy-module/5.2" = "These stubs type `libraries.load` as returning `None`, so the `with` is reported too."
# ///
"""An add-on that ships a `.blend` file loads data-blocks from it with `bpy.data.libraries.load`: the names in
`data_to.materials` before the block ends, the loaded materials after it. The stubs type both sides of the load as
`Any`, so nothing about the file is checked: a name it does not hold is not reported, and after the block
`data_to.materials` keeps the type of the list of names the code assigned."""

# catalog: hide
from typing import assert_type

# catalog: show
from pathlib import Path

import bpy
from bpy.types import Material

ASSETS = Path(__file__).parent / "assets.blend"


def load_rust() -> None:
    with bpy.data.libraries.load(str(ASSETS)) as (data_from, data_to):
        data_to.materials = ["Rust"]
    # gap: what the load gives is not typed
    assert_type(data_to.materials, list[Material])
