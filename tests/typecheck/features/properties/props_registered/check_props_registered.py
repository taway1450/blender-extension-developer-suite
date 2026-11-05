"""Registered properties are attributes of the class they are assigned to and of its subclasses."""

from __future__ import annotations

from typing import Literal, assert_type

import bpy
from bpy.types import (Bone, Camera, Collection, Context, EditBone, Image, Material, NodeSocketFloat, Object,
                       PoseBone, Scene, ShaderNodeMath, Strip, ViewLayer, WindowManager, bpy_prop_collection_idprop)

from . import PROPS_REGISTERED_Item


def on_scene(scene: Scene) -> None:
    assert_type(scene.reg_int, int)
    assert_type(scene.reg_mode, Literal["A", "B"])
    assert_type(scene.reg_group, PROPS_REGISTERED_Item)
    assert_type(scene.reg_items, bpy_prop_collection_idprop[PROPS_REGISTERED_Item])
    assert_type(scene.reg_object, Object | None)
    assert_type(scene.reg_id, int)
    scene.reg_int = 2
    scene.reg_int = "2"  # ty: ignore[invalid-assignment]
    scene.reg_mode = "C"  # ty: ignore[invalid-assignment]
    scene.reg_float  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it


def on_ids(obj: Object, material: Material, camera: Camera, collection: Collection, image: Image) -> None:
    assert_type(obj.reg_float, float)
    assert_type(obj.reg_id, int)
    assert_type(material.reg_str, str)
    assert_type(material.reg_id, int)
    assert_type(camera.reg_module_level, int)
    assert_type(collection.reg_alias, str)
    assert_type(image.reg_setattr, float)
    obj.reg_str  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it


def on_other_structs(wm: WindowManager, bone: Bone, edit_bone: EditBone, pose_bone: PoseBone,
                     node: ShaderNodeMath, socket: NodeSocketFloat, view_layer: ViewLayer, strip: Strip) -> None:
    assert_type(wm.reg_bool, bool)
    assert_type(bone.reg_bone, int)
    assert_type(edit_bone.reg_edit_bone, int)
    assert_type(pose_bone.reg_pose_bone, int)
    assert_type(node.reg_node, int)
    assert_type(socket.reg_socket, int)
    assert_type(view_layer.reg_view_layer, int)
    assert_type(strip.reg_strip, int)


def through_data(context: Context) -> None:
    assert_type(bpy.data.scenes[0].reg_int, int)
    assert_type(bpy.data.objects["Cube"].reg_float, float)
    if context.scene is not None:
        assert_type(context.scene.reg_int, int)
