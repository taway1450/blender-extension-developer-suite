"""Registered properties are attributes of the class they are assigned to and of its subclasses."""

from __future__ import annotations

from typing import Literal, TypeVar, assert_type

import bpy
from bpy.types import (Area, Bone, Camera, Collection, Context, EditBone, Image, Material, NodeSocketFloat, Object,
                       PoseBone, Scene, ShaderNodeMath, Strip, ViewLayer, WindowManager, World,
                       bpy_prop_collection_idprop)

from . import PROPS_REGISTERED_Item, PROPS_REGISTERED_WorldSettings

SceneT = TypeVar("SceneT", bound=Scene)
SceneOrObjectT = TypeVar("SceneOrObjectT", Scene, Object)


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
    # A PropertyGroup pointer, a collection and a READ_ONLY property cannot be written, even with their own value.
    assert_type(scene.reg_locked, int)
    scene.reg_group = scene.reg_group  # ty: ignore[invalid-assignment]
    scene.reg_items = scene.reg_items  # ty: ignore[invalid-assignment]
    scene.reg_locked = scene.reg_locked  # ty: ignore[invalid-assignment]
    scene.reg_object = None  # an ID pointer stays writable
    scene.reg_float  # ty: ignore[missing-attribute]  # bare-ok: must stay missing: ty-blender must not add it


def on_narrowed(scene: Scene) -> None:
    """A write through an intersection: the scene after a truth test, or after hasattr."""
    if scene:
        scene.reg_int = 3  # `Scene & ~AlwaysFalsy`
        scene.reg_int = "3"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the write above needs the checker
    if hasattr(scene, "other_addon_value"):
        scene.reg_int = 4  # `Scene & <Protocol with other_addon_value>`


def on_ids(obj: Object, material: Material, camera: Camera, collection: Collection, image: Image) -> None:
    assert_type(obj.reg_float, float)
    assert_type(obj.reg_id, int)
    assert_type(material.reg_str, str)
    assert_type(material.reg_id, int)
    assert_type(camera.reg_module_level, int)
    assert_type(collection.reg_alias, str)
    assert_type(image.reg_setattr, float)
    obj.reg_str  # ty: ignore[missing-attribute]  # bare-ok: must stay missing: ty-blender must not add it


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


def on_unsupported_targets(area: Area) -> None:
    # Blender keeps a property assigned to Area as a plain class attribute; an instance has no such property.
    area.reg_area  # ty: ignore[missing-attribute]  # bare-ok: must stay missing: ty-blender must not add it


def most_derived_owner(scene: Scene, obj: Object) -> None:
    """ID and Scene both register reg_owner_first and reg_owner_last, in opposite orders: Scene's wins on a Scene."""
    assert_type(scene.reg_owner_first, str)
    assert_type(scene.reg_owner_last, str)
    assert_type(obj.reg_owner_first, int)
    assert_type(obj.reg_owner_last, int)


def through_union(either: Scene | Object) -> None:
    assert_type(either.reg_id, int)  # every arm has it
    either.reg_id = 2  # a write goes to every arm
    either.reg_id = "2"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the write above needs the checker


def through_partly_unknown(scene: Scene, other, flag: bool) -> None:
    """A write through a union with an unknown arm, as on an item of a list that typed and untyped code filled."""
    either = scene if flag else other  # `Scene | Unknown`
    either.reg_int = 5
    either.reg_int = "5"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the write above needs the checker
    either.reg_locked = 5  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing
    for item in [scene] if flag else other:
        item.reg_int = 6


def through_bound(scene: SceneT) -> SceneT:
    assert_type(scene.reg_int, int)
    return scene


def through_constraints(either: SceneOrObjectT) -> SceneOrObjectT:
    assert_type(either.reg_id, int)  # every constraint has it
    return either


def on_the_class(scene_class: type[Scene]) -> None:
    """A class read gives the property declaration (_PropertyDeferred), not the value: the checker leaves it missing."""
    Scene.reg_int  # ty: ignore[missing-attribute]  # oracle-skip: the reference stubs declare it on the class  # bare-ok: must stay missing: a class read is not the value
    scene_class.reg_int  # ty: ignore[missing-attribute]  # oracle-skip: the reference stubs declare it on the class  # bare-ok: must stay missing: a class read is not the value


def through_data(context: Context) -> None:
    assert_type(bpy.data.scenes[0].reg_int, int)
    assert_type(bpy.data.objects["Cube"].reg_float, float)
    if context.scene is not None:
        assert_type(context.scene.reg_int, int)


def on_world(world: World) -> None:
    # Registered by the register() classmethod Blender calls, on the class the registered subclass names.
    assert_type(world.reg_host_settings, PROPS_REGISTERED_WorldSettings)
    assert_type(world.reg_host_settings.level, int)  # oracle-skip: stock ty reads the annotation as the IntProperty call
