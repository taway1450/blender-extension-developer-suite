"""Feature test: the Assumption rules configured for one add-on.

`tests/typecheck/ty.toml` has an `[[overrides]]` entry for this add-on that sets the category `blender-assumptions` to
`error` and the rule `blender-assumed-context-member` to `ignore`: the rule's own level wins over its category's. An
ignored rule still narrows, so the helper's read below is neither reported nor an error."""

import bpy
from bpy.types import UIList


def frame() -> int:
    return bpy.context.scene.frame_current  # blender-assumed-context-member is ignored here


class ASM_CONFIG_UL_items(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name")  # ty: ignore[blender-assumed-list-item]


classes = (ASM_CONFIG_UL_items,)
register, unregister = bpy.utils.register_classes_factory(classes)
