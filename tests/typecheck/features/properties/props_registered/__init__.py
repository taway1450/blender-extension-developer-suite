"""Feature test: properties assigned to Blender's own classes (bpy.types.X.name = Property(...)).

Every ID type and the structs with ID properties (bones, nodes, sockets, view layers, strips) accept them.
Other structs do not: the assignment silently becomes a plain class attribute holding the deferred property.
"""

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import Collection as Coll
from bpy.types import PropertyGroup


class PROPS_REGISTERED_Item(PropertyGroup):
    label: StringProperty()


DYNAMIC = {"dyn_a": IntProperty(), "dyn_b": FloatProperty()}

# Registered when the module is imported, not in register(): still a property of Camera.
bpy.types.Camera.reg_module_level = IntProperty()


def register():
    bpy.utils.register_class(PROPS_REGISTERED_Item)
    bpy.types.Scene.reg_int = IntProperty()
    bpy.types.Scene.reg_mode = EnumProperty(items=[("A", "A", ""), ("B", "B", "")])
    bpy.types.Scene.reg_group = PointerProperty(type=PROPS_REGISTERED_Item)
    bpy.types.Scene.reg_items = CollectionProperty(type=PROPS_REGISTERED_Item)
    bpy.types.Scene.reg_object = PointerProperty(type=bpy.types.Object)
    bpy.types.Object.reg_float = FloatProperty()
    bpy.types.Material.reg_str = StringProperty()
    bpy.types.WindowManager.reg_bool = BoolProperty()
    bpy.types.ID.reg_id = IntProperty()  # every ID type: Scene, Object, Material, ...
    # The same name on a class and on its base: the most-derived class wins, whichever is registered first.
    bpy.types.ID.reg_owner_first = IntProperty()
    bpy.types.Scene.reg_owner_first = StringProperty()
    bpy.types.Scene.reg_owner_last = StringProperty()
    bpy.types.ID.reg_owner_last = IntProperty()
    bpy.types.Bone.reg_bone = IntProperty()
    bpy.types.EditBone.reg_edit_bone = IntProperty()
    bpy.types.PoseBone.reg_pose_bone = IntProperty()
    bpy.types.Node.reg_node = IntProperty()  # every node class
    bpy.types.NodeSocket.reg_socket = IntProperty()
    bpy.types.ViewLayer.reg_view_layer = IntProperty()
    bpy.types.Strip.reg_strip = IntProperty()
    Coll.reg_alias = StringProperty()  # through an import alias
    setattr(bpy.types.Image, "reg_setattr", FloatProperty())  # setattr with a literal name
    for name, prop in DYNAMIC.items():
        setattr(bpy.types.Text, name, prop)  # computed names: not known to the checker, and not required
    bpy.types.Area.reg_area = IntProperty()  # ty: ignore[blender-unsupported-property-target]
    bpy.types.Modifier.reg_modifier = IntProperty()  # ty: ignore[blender-unsupported-property-target]
    bpy.types.Window.reg_window = IntProperty()  # ty: ignore[blender-unsupported-property-target]
    bpy.types.Preferences.reg_preferences = IntProperty()  # ty: ignore[blender-unsupported-property-target]
    bpy.types.SpaceView3D.reg_space = IntProperty()  # ty: ignore[blender-unsupported-property-target]
    bpy.types.Context.reg_context = IntProperty()  # ty: ignore[blender-unsupported-property-target]


def unregister():
    for cls, name in [(bpy.types.Scene, "reg_int"), (bpy.types.Scene, "reg_mode"), (bpy.types.Scene, "reg_group"),
                      (bpy.types.Scene, "reg_items"), (bpy.types.Scene, "reg_object"),
                      (bpy.types.Object, "reg_float"), (bpy.types.Material, "reg_str"),
                      (bpy.types.WindowManager, "reg_bool"), (bpy.types.ID, "reg_id"),
                      (bpy.types.ID, "reg_owner_first"), (bpy.types.Scene, "reg_owner_first"),
                      (bpy.types.Scene, "reg_owner_last"), (bpy.types.ID, "reg_owner_last"),
                      (bpy.types.Bone, "reg_bone"), (bpy.types.EditBone, "reg_edit_bone"),
                      (bpy.types.PoseBone, "reg_pose_bone"), (bpy.types.Node, "reg_node"),
                      (bpy.types.NodeSocket, "reg_socket"), (bpy.types.ViewLayer, "reg_view_layer"),
                      (bpy.types.Strip, "reg_strip"), (Coll, "reg_alias"), (bpy.types.Image, "reg_setattr"),
                      (bpy.types.Text, "dyn_a"), (bpy.types.Text, "dyn_b"), (bpy.types.Camera, "reg_module_level"),
                      (bpy.types.Area, "reg_area"), (bpy.types.Modifier, "reg_modifier"),
                      (bpy.types.Window, "reg_window"), (bpy.types.Preferences, "reg_preferences"),
                      (bpy.types.SpaceView3D, "reg_space"), (bpy.types.Context, "reg_context")]:
        delattr(cls, name)
    bpy.utils.unregister_class(PROPS_REGISTERED_Item)
