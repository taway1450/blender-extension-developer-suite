"""Reference stub of props_hosts."""

from bpy.types import (AddonPreferences, AssetShelf, FileHandler, Gizmo, Header, KeyConfigPreferences, KeyingSetInfo,
                       Macro, Menu, Node, NodeSocket, NodeTree, NodeTreeInterfaceSocket, Operator, OperatorProperties,
                       Panel, PropertyGroup, RenderEngine, UIList)

class PROPS_HOSTS_Group(PropertyGroup):
    value: int

class _OperatorProperties(OperatorProperties):
    value: int

class PROPS_HOSTS_OT_operator(Operator):
    value: int
    properties: _OperatorProperties  # type: ignore[assignment]

class PROPS_HOSTS_OT_macro(Macro):
    value: int

class PROPS_HOSTS_Preferences(AddonPreferences):
    value: int

class PROPS_HOSTS_UL_list(UIList):
    value: int

class PROPS_HOSTS_Tree(NodeTree):
    value: int

class PROPS_HOSTS_Socket(NodeSocket):
    value: int

class PROPS_HOSTS_InterfaceSocket(NodeTreeInterfaceSocket):
    value: int

class PROPS_HOSTS_KeyConfigPreferences(KeyConfigPreferences):
    value: int

class PROPS_HOSTS_Node(Node):
    value: int

class PROPS_HOSTS_GT_gizmo(Gizmo):
    value: int

class PROPS_HOSTS_PT_panel(Panel): ...
class PROPS_HOSTS_MT_menu(Menu): ...
class PROPS_HOSTS_HT_header(Header): ...
class PROPS_HOSTS_KSI_keying_set(KeyingSetInfo): ...
class PROPS_HOSTS_RenderEngine(RenderEngine): ...
class PROPS_HOSTS_FH_handler(FileHandler): ...
class PROPS_HOSTS_AST_shelf(AssetShelf): ...

def register() -> None: ...
def unregister() -> None: ...
