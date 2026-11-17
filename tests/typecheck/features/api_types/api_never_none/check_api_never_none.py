"""A pointer to a struct embedded by value is never None; a DNA pointer can be, the context's preferences and window
manager never are. Callers of the callbacks pass a context, which only RenderEngine.view_draw accepts as None, and the
other parameters Blender always fills."""

from __future__ import annotations

from typing import assert_type

from bpy.types import (AnimData, AssetShelf, Camera, CameraDOFSettings, ColorManagedViewSettings, Context, Depsgraph,
                       FFmpegSettings, Header, ImagePaint, KeyingSetInfo, Menu, Object, Pose, Preferences,
                       RenderEngine, RenderSettings, Scene, SceneEEVEE, Sculpt, ToolSettings, UILayout, UIList,
                       WindowManager)

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
