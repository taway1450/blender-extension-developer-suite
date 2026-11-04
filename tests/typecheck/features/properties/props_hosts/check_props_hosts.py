"""Where an annotation becomes a property, the attribute has the property's type; elsewhere it does not exist."""

from __future__ import annotations

from typing import assert_type

from . import (PROPS_HOSTS_AST_shelf, PROPS_HOSTS_FH_handler, PROPS_HOSTS_GT_gizmo, PROPS_HOSTS_Group,
               PROPS_HOSTS_HT_header, PROPS_HOSTS_KSI_keying_set, PROPS_HOSTS_MT_menu, PROPS_HOSTS_Node,
               PROPS_HOSTS_OT_macro, PROPS_HOSTS_OT_operator, PROPS_HOSTS_Preferences, PROPS_HOSTS_PT_panel,
               PROPS_HOSTS_RenderEngine, PROPS_HOSTS_Socket, PROPS_HOSTS_Tree, PROPS_HOSTS_UL_list)


def accepted(group: PROPS_HOSTS_Group, op: PROPS_HOSTS_OT_operator, macro: PROPS_HOSTS_OT_macro,
             prefs: PROPS_HOSTS_Preferences, ui_list: PROPS_HOSTS_UL_list, tree: PROPS_HOSTS_Tree,
             socket: PROPS_HOSTS_Socket, node: PROPS_HOSTS_Node, gizmo: PROPS_HOSTS_GT_gizmo) -> None:
    assert_type(group.value, int)
    assert_type(op.value, int)
    assert_type(op.properties.value, int)
    assert_type(macro.value, int)
    assert_type(prefs.value, int)
    assert_type(ui_list.value, int)
    assert_type(tree.value, int)
    assert_type(socket.value, int)
    assert_type(node.value, int)
    assert_type(gizmo.value, int)


def ignored(panel: PROPS_HOSTS_PT_panel, menu: PROPS_HOSTS_MT_menu, header: PROPS_HOSTS_HT_header,
            keying_set: PROPS_HOSTS_KSI_keying_set, engine: PROPS_HOSTS_RenderEngine,
            handler: PROPS_HOSTS_FH_handler, shelf: PROPS_HOSTS_AST_shelf) -> None:
    panel.value  # ty: ignore[unresolved-attribute]
    menu.value  # ty: ignore[unresolved-attribute]
    header.value  # ty: ignore[unresolved-attribute]
    keying_set.value  # ty: ignore[unresolved-attribute]
    engine.value  # ty: ignore[unresolved-attribute]
    handler.value  # ty: ignore[unresolved-attribute]
    shelf.value  # ty: ignore[unresolved-attribute]
