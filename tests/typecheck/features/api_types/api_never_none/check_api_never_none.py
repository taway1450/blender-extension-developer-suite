"""A pointer to a struct embedded by value is never None; a DNA pointer can be, the context's preferences and window
manager never are, nor are the pointers and function results Blender always sets (probed in #109). Callers of the callbacks pass a context, which only RenderEngine.view_draw accepts as None, and the
other parameters Blender always fills."""

from __future__ import annotations

from typing import assert_type

from bpy.types import (ID, AnimData, AssetLibraryCollection, AssetMetaData, AssetRepresentation, AssetShelf,
                       BlendDataMeshes, BlendDataNodeTrees, BlendDataObjects, Bone, BoneColor, Camera,
                       CameraDOFSettings, ColorManagedViewSettings, Context, Depsgraph, DepsgraphObjectInstance,
                       DepsgraphUpdate, EditBone, FFmpegSettings, GeometryNodeTree, Header, ImagePaint, KeyConfig,
                       KeyConfigurations,
                       KeyingSetInfo, Material, Menu, Mesh, MovieTracking, MovieTrackingObject, MovieTrackingObjects,
                       MovieTrackingReconstruction, Node, NodeInternalLink, NodeLink, NodeSocket, NodeTree, Object,
                       ParticleSettings, Pose, PoseBone, Preferences, RegionView3D, RenderEngine, RenderSettings,
                       RenderViews, Scene, SceneEEVEE, SceneRenderView, Sculpt, SpaceView3D, ToolSettings, UILayout,
                       UIList, UserAssetLibrary, ViewLayer, WindowManager, World, XrSessionState, XrViewfinderState)
from idprop.types import IDPropertyUIManager

from . import API_NEVER_NONE_AST_shelf, API_NEVER_NONE_Engine, API_NEVER_NONE_KSI_keying_set, API_NEVER_NONE_MT_menu


def embedded(camera: Camera, scene: Scene, render: RenderSettings, tool_settings: ToolSettings) -> None:
    assert_type(camera.dof, CameraDOFSettings)  # bare-ok: a stub fact: the struct is a member of Camera
    assert_type(scene.view_settings, ColorManagedViewSettings)  # bare-ok: a stub fact: the struct is a member of Scene
    assert_type(scene.eevee, SceneEEVEE)  # bare-ok: a stub fact: the struct is a member of Scene
    assert_type(render.ffmpeg, FFmpegSettings)  # bare-ok: a stub fact: the struct is a member of RenderSettings
    assert_type(tool_settings.image_paint, ImagePaint)  # bare-ok: a stub fact: the struct is a member of ToolSettings


def context_pointers(context: Context) -> None:
    assert_type(context.preferences, Preferences)  # bare-ok: a stub fact: always the global preferences
    assert_type(context.window_manager, WindowManager)  # bare-ok: a stub fact: the window manager exists whenever Python runs


def dna_pointers(ob: Object, tool_settings: ToolSettings) -> None:
    assert_type(tool_settings.sculpt, Sculpt | None)  # bare-ok: allocated on first use, None on a new scene
    assert_type(ob.pose, Pose | None)  # bare-ok: None unless the object is an armature
    assert_type(ob.animation_data, AnimData | None)  # bare-ok: None until animation_data_create()


def always_set(xr: XrSessionState, keyconfigs: KeyConfigurations, link: NodeLink, internal_link: NodeInternalLink,
               bone: Bone, pose_bone: PoseBone, edit_bone: EditBone, tracking: MovieTracking,
               tracking_object: MovieTrackingObject, tracking_objects: MovieTrackingObjects, space: SpaceView3D,
               asset: AssetRepresentation, depsgraph: Depsgraph, instance: DepsgraphObjectInstance,
               update: DepsgraphUpdate, material: Material, world: World) -> None:
    assert_type(xr.viewfinder, XrViewfinderState)  # bare-ok: a stub fact: null only when there is no XR session state
    assert_type(keyconfigs.active, KeyConfig)  # bare-ok: a stub fact: falls back to the default key configuration
    assert_type(keyconfigs.default, KeyConfig)  # bare-ok: a stub fact: the window manager always has one
    assert_type(keyconfigs.addon, KeyConfig)  # bare-ok: a stub fact: the window manager always has one
    assert_type(keyconfigs.user, KeyConfig)  # bare-ok: a stub fact: the window manager always has one
    assert_type(link.from_node, Node)  # bare-ok: a stub fact: a link always has both ends
    assert_type(link.to_node, Node)  # bare-ok: a stub fact: a link always has both ends
    assert_type(link.from_socket, NodeSocket)  # bare-ok: a stub fact: a link always has both ends
    assert_type(link.to_socket, NodeSocket)  # bare-ok: a stub fact: a link always has both ends
    assert_type(internal_link.from_socket, NodeSocket)  # bare-ok: a stub fact: a link always has both ends
    assert_type(internal_link.to_socket, NodeSocket)  # bare-ok: a stub fact: a link always has both ends
    assert_type(bone.color, BoneColor)  # bare-ok: a stub fact: the struct is a member of Bone
    assert_type(pose_bone.color, BoneColor)  # bare-ok: a stub fact: the struct is a member of PoseBone
    assert_type(edit_bone.color, BoneColor)  # bare-ok: a stub fact: the struct is a member of EditBone
    assert_type(tracking.reconstruction, MovieTrackingReconstruction)  # bare-ok: a stub fact: the camera object's, which can't be removed
    assert_type(tracking_object.reconstruction, MovieTrackingReconstruction)  # bare-ok: a stub fact: the struct is a member of MovieTrackingObject
    assert_type(tracking_objects.active, MovieTrackingObject)  # bare-ok: a stub fact: active_object_index is clamped to the objects
    assert_type(space.region_3d, RegionView3D)  # bare-ok: a stub fact: the main region of the space
    assert_type(asset.metadata, AssetMetaData)  # bare-ok: a stub fact: every asset has metadata
    assert_type(depsgraph.scene, Scene)  # bare-ok: a stub fact: a depsgraph is built for a scene
    assert_type(depsgraph.scene_eval, Scene)  # bare-ok: a stub fact: a depsgraph is built for a scene
    assert_type(depsgraph.view_layer, ViewLayer)  # bare-ok: a stub fact: a depsgraph is built for a view layer
    assert_type(depsgraph.view_layer_eval, ViewLayer)  # bare-ok: a stub fact: a depsgraph is built for a view layer
    assert_type(instance.object, Object)  # bare-ok: a stub fact: every instance is of an object
    assert_type(update.id, ID)  # bare-ok: a stub fact: every update is of an ID
    assert_type(material.node_tree, NodeTree)  # bare-ok: a stub fact: every material has a node tree since 5.0
    assert_type(world.node_tree, NodeTree)  # bare-ok: a stub fact: every world has a node tree since 5.0


def active_members(views: RenderViews, particles: ParticleSettings) -> None:
    assert_type(views.active, SceneRenderView)  # bare-ok: a stub fact: a scene always has a render view
    assert_type(particles.active_texture_index, int)  # bare-ok: a stub fact: an index, not a pointer


def stay_nullable(wm: WindowManager, instance: DepsgraphObjectInstance) -> None:
    assert_type(wm.xr_session_state, XrSessionState | None)  # bare-ok: None without a VR session
    assert_type(instance.instance_object, Object | None)  # bare-ok: None unless the object is an instance
    assert_type(instance.parent, Object | None)  # bare-ok: None unless the object is an instance


def always_returned(node_groups: BlendDataNodeTrees, libraries: AssetLibraryCollection, objects: BlendDataObjects,
                    meshes: BlendDataMeshes, ob: Object, depsgraph: Depsgraph) -> None:
    # A stub fact (an unknown type raises), and the constructor narrowing, which a stub cannot state.
    assert_type(node_groups.new("Tree", "GeometryNodeTree"), GeometryNodeTree)  # oracle-skip: narrowed by ty-blender
    assert_type(libraries.new(), UserAssetLibrary)  # bare-ok: a stub fact: a failure raises
    assert_type(objects.new("Object", None), Object)  # bare-ok: a stub fact: a failure raises
    assert_type(meshes.new_from_object(ob), Mesh)  # bare-ok: a stub fact: a failure raises
    assert_type(ob.id_properties_ui("prop"), IDPropertyUIManager)  # bare-ok: a stub fact: a failure raises


def callers(menu: Menu, header: Header, ui_list: UIList, engine: RenderEngine, context: Context, layout: UILayout,
            depsgraph: Depsgraph) -> None:
    menu.draw(None)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes a context
    header.draw(None)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes a context
    ui_list.draw_filter(None, layout)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes a context
    engine.view_update(None, depsgraph)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes a context
    assert_type(engine.view_draw(None, depsgraph), None)  # bare-ok: a stub fact: None when drawn off-screen


def filled_parameters(ui_list: UIList, engine: RenderEngine, ksi: KeyingSetInfo, shelf: AssetShelf, context: Context,
                      layout: UILayout) -> None:
    ui_list.draw_item(context, layout, None, None, 0, None, "", 0, 0)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes the data
    ui_list.filter_items(context, None, "items")  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes the data
    engine.render(None)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes a depsgraph
    engine.view_draw(context, None)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes a depsgraph
    ksi.iterator(context, None)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes a keying set
    shelf.asset_poll(None)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes an asset
    shelf.draw_context_menu(context, None, layout)  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: Blender always passes an asset


def overrides(menu: API_NEVER_NONE_MT_menu, engine: API_NEVER_NONE_Engine, ksi: API_NEVER_NONE_KSI_keying_set,
              shelf: type[API_NEVER_NONE_AST_shelf], context: Context, depsgraph: Depsgraph) -> None:
    menu.draw(None)  # ty: ignore[invalid-argument-type]
    engine.view_update(None, depsgraph)  # ty: ignore[invalid-argument-type]
    assert_type(engine.view_draw(None, depsgraph), None)
    engine.render(None)  # ty: ignore[invalid-argument-type]
    ksi.iterator(context, None)  # ty: ignore[invalid-argument-type]
    shelf.asset_poll(None)  # ty: ignore[invalid-argument-type]
