# /// catalog
# title = "`obj[\"key\"]`"
# section = "custom-properties"
# status = "not-handled"
# blender-docs = ["info_quickstart"]
#
# [future]
# class = "not-checkable"
# note = "Custom properties are added by any script, the user or a file while Blender runs, so no static tool knows which keys a data-block has."
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `Object.__getitem__` as taking an `int`, so a key by name is reported."
# ///
"""Custom properties, set and read with `obj["key"]` on a data-block and on some other structs such as bones, are not
known before Blender runs. A script, the user in the Custom Properties panel or the loaded file adds them, so whether a
key exists and what it holds is decided then; the stubs accept any key."""

from bpy.types import Object


def example(ob: Object) -> None:
    ob["scatter_seed"] = 7
    print(ob["scatter_seed"] + 1)
