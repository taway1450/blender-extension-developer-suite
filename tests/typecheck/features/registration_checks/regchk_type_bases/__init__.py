"""Feature test: a Menu that is only the base of menus made with ``type(name, (Base,), namespace)``, as rigify's
``ArmatureSubMenu``. Blender never sees the base itself, so it needs neither a ``bl_idname`` nor registration, while
the menus made from it are registered through a list the checker cannot follow (it gives up)."""

import bpy
from bpy.types import Menu


class SubMenuBase(Menu):
    bl_label = "Sub menu"

    def draw(self, context):
        self.layout.label(text=self.bl_label)


def make_menus():
    menus = []
    for name in ("first", "second"):
        idname = "REGCHK_TYPE_BASES_MT_" + name
        menus.append(type(idname, (SubMenuBase,), {"bl_idname": idname, "bl_label": name}))
    return menus


MENUS = make_menus()


def register():
    for menu in MENUS:
        bpy.utils.register_class(menu)


def unregister():
    for menu in reversed(MENUS):
        bpy.utils.unregister_class(menu)
