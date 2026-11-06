"""Feature test: property annotations on every kind of class Blender registers.

Accepted (Blender 5.4): PropertyGroup, Operator, Macro, AddonPreferences, UIList, Node, NodeSocket, NodeTree,
NodeTreeInterfaceSocket, KeyConfigPreferences and Gizmo (stored in its properties, read through the instance like an
operator's). Ignored without an error: Panel,
Menu, Header, KeyingSetInfo, RenderEngine, FileHandler, AssetShelf; the annotation stays a plain annotation and
reading the attribute raises AttributeError.
"""

import bpy
from bpy.props import IntProperty
from bpy.types import (AddonPreferences, AssetShelf, FileHandler, Gizmo, Header, KeyConfigPreferences, KeyingSetInfo,
                       Macro, Menu, Node, NodeSocket, NodeTree, NodeTreeInterfaceSocket, Operator, Panel, PropertyGroup,
                       RenderEngine, UIList)


class PROPS_HOSTS_Group(PropertyGroup):
    value: IntProperty()


class PROPS_HOSTS_OT_operator(Operator):
    bl_idname = "props_hosts.operator"
    bl_label = "Operator"

    value: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class PROPS_HOSTS_OT_macro(Macro):
    bl_idname = "props_hosts.macro"
    bl_label = "Macro"

    value: IntProperty()


class PROPS_HOSTS_Preferences(AddonPreferences):
    bl_idname = __package__

    value: IntProperty()


class PROPS_HOSTS_UL_list(UIList):
    value: IntProperty()

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.label(text=str(self.value))


class PROPS_HOSTS_Tree(NodeTree):
    bl_idname = "PROPS_HOSTS_Tree"
    bl_label = "Feature test tree"
    bl_icon = "NODETREE"

    value: IntProperty()


class PROPS_HOSTS_Socket(NodeSocket):
    bl_idname = "PROPS_HOSTS_Socket"
    bl_label = "Feature test socket"

    value: IntProperty()

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (1.0, 1.0, 1.0, 1.0)


class PROPS_HOSTS_InterfaceSocket(NodeTreeInterfaceSocket):
    bl_socket_idname = "PROPS_HOSTS_Socket"

    value: IntProperty()


class PROPS_HOSTS_KeyConfigPreferences(KeyConfigPreferences):
    bl_idname = "PROPS_HOSTS_keyconfig"

    value: IntProperty()


class PROPS_HOSTS_Node(Node):
    bl_idname = "PROPS_HOSTS_Node"
    bl_label = "Feature test node"

    value: IntProperty()


class PROPS_HOSTS_GT_gizmo(Gizmo):
    bl_idname = "PROPS_HOSTS_GT_gizmo"

    value: IntProperty()

    def draw(self, context):
        pass


class PROPS_HOSTS_PT_panel(Panel):
    bl_idname = "PROPS_HOSTS_PT_panel"
    bl_label = "Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    value: IntProperty()  # ty: ignore[blender-unsupported-property-host]

    def draw(self, context):
        pass


class PROPS_HOSTS_MT_menu(Menu):
    bl_idname = "PROPS_HOSTS_MT_menu"
    bl_label = "Menu"

    value: IntProperty()  # ty: ignore[blender-unsupported-property-host]

    def draw(self, context):
        pass


class PROPS_HOSTS_HT_header(Header):
    bl_idname = "PROPS_HOSTS_HT_header"
    bl_space_type = "VIEW_3D"

    value: IntProperty()  # ty: ignore[blender-unsupported-property-host]

    def draw(self, context):
        pass


class PROPS_HOSTS_KSI_keying_set(KeyingSetInfo):
    bl_idname = "PROPS_HOSTS_KSI_keying_set"
    bl_label = "Keying set"

    value: IntProperty()  # ty: ignore[blender-unsupported-property-host]

    def poll(self, context):
        return True

    def iterator(self, context, ks):
        pass

    def generate(self, context, ks, data):
        pass


class PROPS_HOSTS_RenderEngine(RenderEngine):
    bl_idname = "PROPS_HOSTS_RENDER"
    bl_label = "Render engine"

    value: IntProperty()  # ty: ignore[blender-unsupported-property-host]


class PROPS_HOSTS_FH_handler(FileHandler):
    bl_idname = "PROPS_HOSTS_FH_handler"
    bl_label = "File handler"
    bl_file_extensions = ".txt"

    value: IntProperty()  # ty: ignore[blender-unsupported-property-host]


class PROPS_HOSTS_AST_shelf(AssetShelf):
    bl_idname = "PROPS_HOSTS_AST_shelf"
    bl_space_type = "VIEW_3D"

    value: IntProperty()  # ty: ignore[blender-unsupported-property-host]


classes = (PROPS_HOSTS_Group, PROPS_HOSTS_OT_operator, PROPS_HOSTS_OT_macro, PROPS_HOSTS_Preferences,
           PROPS_HOSTS_UL_list, PROPS_HOSTS_Tree, PROPS_HOSTS_Socket, PROPS_HOSTS_InterfaceSocket,
           PROPS_HOSTS_KeyConfigPreferences, PROPS_HOSTS_Node, PROPS_HOSTS_GT_gizmo,
           PROPS_HOSTS_PT_panel, PROPS_HOSTS_MT_menu, PROPS_HOSTS_HT_header, PROPS_HOSTS_KSI_keying_set,
           PROPS_HOSTS_RenderEngine, PROPS_HOSTS_FH_handler, PROPS_HOSTS_AST_shelf)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
