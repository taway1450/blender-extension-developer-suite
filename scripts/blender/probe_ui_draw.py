"""Draw the ``bl_ui`` panels and menus that raised in a rare state, in that state (run by scripts/probe_ui_draw.py,
#148).

Usage (inside Blender):
  blender --background --factory-startup --python probe_ui_draw.py -- <output json>

Each check builds its state from factory startup and calls the class's ``draw`` (or ``draw_header``) with:

- a ``self`` that reads the registered class and has a recording ``layout``. Like Blender's ``UILayout``, the
  layout raises ``TypeError`` when an RNA pointer argument (``prop()``'s ``data``, ``prop_search()``'s
  ``search_data``, ``template_list()``'s data, ...) is None, and ``AttributeError`` when a Blender struct has no
  property of the given name;
- a context that gives the state's members and takes every other member from ``bpy.context``.

The class's ``poll``, and that of its parent panel, must accept the state (else the check fails: the state is not
reachable that way). A check fails when the draw raises. The states:

- ``no-brush``: a paint mode whose paint settings have no brush, as after the active brush is deleted (the Outliner's
  Blender File view) or its asset library is missing. The probe enters the mode on the default cube or a new Grease
  Pencil object and removes the brush data-block, which clears the paint settings' brush. Besides the panels, each
  mode's tool settings in the tool header (``_draw_tool_settings_context_mode``, not a registered class) run with a tool
  that uses brushes.
- ``pinned``: a Properties editor pinned to an ID, which leaves the members outside the pinned path None. Pinning
  in the Particles tab pins the particle settings (no ``particle_system``, no ``object``); pinning an object data
  tab pins the data (no ``object``); pinning in the Bone tab pins the armature (no ``object``), while
  ``edit_object`` is still the scene's, here a mesh in edit mode.
- ``no-interface-item``: a node group whose interface has no active item (a new empty group); the interface panel
  always shows its context menu.
- ``no-sequencer-scene``: a workspace without a sequencer scene (its header can unlink it).
- ``no-sequence-editor``: a sequencer scene that has no sequence editor yet (one never given a strip).
- ``no-project``: no project is open while the Project editor shows its Variables section.

Spec #146 H3 (#149) adds states outside ``bl_ui``, with the glTF add-on enabled:

- ``deleted-filter-action``: the glTF exporter's action filter list holds an action deleted since the list was
  filled (its pointer is None); the list's ``draw_item`` and ``filter_items`` (filtered and sorted by name) run.
- ``non-mesh-variant``: the active object is a curve with a material while the glTF material variants UI is on;
  each variant operator whose poll accepts it runs (a poll that raises fails too).
- ``non-camera-scene-camera``: the scene camera is an empty while Freestyle renders in the parameter editor mode
  (the factory line set); the render must run ``parameter_editor.process()`` without raising.

The JSON maps each ``<state>: <class>.<function>`` to its result (``ok``, ``value`` or ``error``); the driver reads
it.
"""

from __future__ import annotations

import os
import sys
import traceback
import types

import addon_utils
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _recorder import check, script_args, write_results
from _stub_ui import Context, ProbeError, StandIn, StubLayout


def draw(name: str, context: Context, function: str = "draw") -> str:
    """Check the polls of the class ``name`` (and its parent panel) in ``context``, then call its ``function``."""
    cls = getattr(bpy.types, name)
    parent = getattr(cls, "bl_parent_id", "")
    for poller in (cls, getattr(bpy.types, parent) if parent else None):
        if poller is not None and hasattr(poller, "poll") and not poller.poll(context):
            raise ProbeError(f"{poller.__name__}.poll() rejects the state")
    getattr(cls, function)(StandIn(cls), context)
    return "drawn"


def reset() -> None:
    bpy.ops.wm.read_homefile(use_factory_startup=True)


# ---------------------------------------------------------------------------------------------------------------
# no-brush


def grease_pencil_object() -> bpy.types.Object:
    data = bpy.data.grease_pencils.new("Probe")
    data.layers.new("Layer")
    obj = bpy.data.objects.new("Probe", data)
    bpy.context.collection.objects.link(obj)
    return obj


def no_brush_context(mode: str, paint_attr: str) -> Context:
    """Enter ``mode`` (the default cube, or a new Grease Pencil object) and remove the paint settings' brush."""
    reset()
    if "GREASE_PENCIL" in mode:
        obj = grease_pencil_object()
    else:
        obj = bpy.data.objects["Cube"]
    view_layer = bpy.context.view_layer
    for other in view_layer.objects:
        other.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode=mode)
    tool_settings = bpy.context.tool_settings
    paint = getattr(tool_settings, paint_attr)
    if paint.brush is None:
        raise ProbeError(f"entering {mode} set no brush")
    bpy.data.brushes.remove(paint.brush)
    if paint.brush is not None:
        raise ProbeError(f"removing the brush left {paint_attr}.brush set")
    return Context(space_data=types.SimpleNamespace(type="VIEW_3D"))


NO_BRUSH = (
    ("SCULPT", "sculpt", ("VIEW3D_PT_sculpt_context_menu", "VIEW3D_PT_sculpt_options_gravity")),
    ("VERTEX_PAINT", "vertex_paint", ("VIEW3D_PT_paint_vertex_context_menu",)),
    ("TEXTURE_PAINT", "image_paint", ("VIEW3D_PT_paint_texture_context_menu",)),
    ("PAINT_GREASE_PENCIL", "gpencil_paint", ("VIEW3D_PT_greasepencil_draw_context_menu",)),
    (
        "SCULPT_GREASE_PENCIL",
        "gpencil_sculpt_paint",
        ("VIEW3D_PT_greasepencil_sculpt_context_menu", "VIEW3D_PT_tools_grease_pencil_sculpt_settings"),
    ),
    ("VERTEX_GREASE_PENCIL", "gpencil_vertex_paint", ("VIEW3D_PT_greasepencil_vertex_paint_context_menu",)),
)

# The header's tool settings (`VIEW3D_HT_tool_header`) per mode: object mode, paint settings, helper (named after
# `context.mode`).
NO_BRUSH_TOOL_SETTINGS = (
    ("SCULPT", "sculpt", "SCULPT"),
    ("VERTEX_PAINT", "vertex_paint", "PAINT_VERTEX"),
    ("WEIGHT_PAINT", "weight_paint", "PAINT_WEIGHT"),
    ("TEXTURE_PAINT", "image_paint", "PAINT_TEXTURE"),
    ("PAINT_GREASE_PENCIL", "gpencil_paint", "PAINT_GREASE_PENCIL"),
    ("SCULPT_GREASE_PENCIL", "gpencil_sculpt_paint", "SCULPT_GREASE_PENCIL"),
    ("WEIGHT_GREASE_PENCIL", "gpencil_weight_paint", "WEIGHT_GREASE_PENCIL"),
    ("VERTEX_GREASE_PENCIL", "gpencil_vertex_paint", "VERTEX_GREASE_PENCIL"),
)


def check_no_brush(results: dict) -> None:
    for mode, paint_attr, names in NO_BRUSH:
        for name in names:

            def run(mode=mode, paint_attr=paint_attr, name=name):
                return draw(name, no_brush_context(mode, paint_attr))

            check(results, f"no-brush {mode}: {name}.draw", run)
    for mode, paint_attr, helper in NO_BRUSH_TOOL_SETTINGS:

        def tool_settings(mode=mode, paint_attr=paint_attr, helper=helper):
            context = no_brush_context(mode, paint_attr)
            from bl_ui.space_view3d import _draw_tool_settings_context_mode

            tool = types.SimpleNamespace(use_brushes=True, idname="builtin.brush")
            return getattr(_draw_tool_settings_context_mode, helper)(context, StubLayout(), tool)

        check(results, f"no-brush {mode}: _draw_tool_settings_context_mode.{helper}", tool_settings)


# ---------------------------------------------------------------------------------------------------------------
# pinned


def pinned_space(pin_id) -> types.SimpleNamespace:
    return types.SimpleNamespace(type="PROPERTIES", pin_id=pin_id, use_pin_id=True)


def engine_of(name: str) -> str:
    """An engine the panel ``name`` lists (`BLENDER_RENDER` stands for the engines that add themselves to such panels,
    as Cycles does)."""
    engines = getattr(getattr(bpy.types, name), "COMPAT_ENGINES", {bpy.context.engine})
    return "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else min(engines)


def pinned_particles(name: str, **settings) -> str:
    reset()
    part = bpy.data.particles.new("Probe")
    for key, value in settings.items():
        setattr(part, key, value)
    context = Context(particle_system=None, object=None, space_data=pinned_space(part), engine=engine_of(name))
    return draw(name, context)


def pinned_data(name: str, member: str, data, function: str = "draw") -> str:
    context = Context(object=None, space_data=pinned_space(data), engine=engine_of(name), **{member: data})
    return draw(name, context, function)


def pinned_bone() -> str:
    reset()
    bpy.ops.object.armature_add()
    armature = bpy.context.active_object.data
    bpy.ops.object.mode_set(mode="OBJECT")
    cube = bpy.data.objects["Cube"]
    bpy.context.view_layer.objects.active = cube
    bpy.ops.object.mode_set(mode="EDIT")
    context = Context(
        object=None,
        armature=armature,
        bone=armature.bones[0],
        edit_bone=None,
        pose_object=None,
        edit_object=bpy.context.edit_object,
        space_data=pinned_space(armature),
    )
    return draw("BONE_PT_collections", context)


def check_pinned(results: dict) -> None:
    check(
        results,
        "pinned particle settings: PARTICLE_PT_render_path_timing.draw",
        lambda: pinned_particles("PARTICLE_PT_render_path_timing", render_type="PATH"),
    )
    check(
        results,
        "pinned particle settings: PARTICLE_PT_physics_fluid_interaction.draw",
        lambda: pinned_particles("PARTICLE_PT_physics_fluid_interaction", physics_type="FLUID"),
    )

    def curves():
        reset()
        return pinned_data("DATA_PT_curves_surface", "curves", bpy.data.hair_curves.new("Probe"))

    check(results, "pinned curves: DATA_PT_curves_surface.draw", curves)
    for name in ("DATA_PT_lightprobe_display", "DATA_PT_lightprobe_display_eevee"):

        def probe(name=name):
            reset()
            return pinned_data(name, "lightprobe", bpy.data.lightprobes.new("Probe", "PLANE"))

        check(results, f"pinned light probe: {name}.draw", probe)

    def lattice():
        reset()
        return pinned_data("DATA_PT_lattice", "lattice", bpy.data.lattices.new("Probe"))

    check(results, "pinned lattice: DATA_PT_lattice.draw", lattice)
    check(results, "pinned armature, mesh in edit mode: BONE_PT_collections.draw", pinned_bone)


# ---------------------------------------------------------------------------------------------------------------
# node editor, sequencer, project


def no_interface_item() -> str:
    reset()
    tree = bpy.data.node_groups.new("Probe", "GeometryNodeTree")
    if tree.interface.active is not None:
        raise ProbeError("a new node group has an active interface item")
    space = types.SimpleNamespace(type="NODE_EDITOR", edit_tree=tree, node_tree=tree)
    return draw("NODE_MT_node_tree_interface_context_menu", Context(space_data=space))


def sequencer_space(view_type: str) -> types.SimpleNamespace:
    overlay = types.SimpleNamespace()
    return types.SimpleNamespace(
        type="SEQUENCE_EDITOR",
        view_type=view_type,
        display_mode="IMAGE",
        proxy_render_size="SCENE",
        show_overlays=True,
        preview_overlay=overlay,
    )


def no_sequence_editor() -> str:
    reset()
    scene = bpy.context.scene
    if scene.sequence_editor is not None:
        scene.sequence_editor_clear()
    context = Context(sequencer_scene=scene, space_data=sequencer_space("PREVIEW"))
    return draw("SEQUENCER_PT_preview_overlay", context)


def check_editors(results: dict) -> None:
    check(results, "no-interface-item: NODE_MT_node_tree_interface_context_menu.draw", no_interface_item)
    for name in ("SEQUENCER_PT_view", "SEQUENCER_MT_view_pie"):

        def run(name=name):
            reset()
            return draw(name, Context(sequencer_scene=None, space_data=sequencer_space("PREVIEW")))

        check(results, f"no-sequencer-scene: {name}.draw", run)
    check(results, "no-sequence-editor: SEQUENCER_PT_preview_overlay.draw", no_sequence_editor)

    def no_project():
        reset()
        if bpy.data.project is not None:
            raise ProbeError("factory startup has a project")
        return draw("PROJECT_PT_variables", Context(space_data=types.SimpleNamespace(type="PROJECT")))

    check(results, "no-project: PROJECT_PT_variables.draw", no_project)


# ---------------------------------------------------------------------------------------------------------------
# add-ons and render modules (#149)


def gltf() -> None:
    addon_utils.enable("io_scene_gltf2", default_set=True, handle_error=None)


def deleted_filter_action() -> str:
    reset()
    gltf()
    from io_scene_gltf2 import on_export_action_filter_changed

    for name in ("Probe", "Other"):
        bpy.data.actions.new(name)
    # Turning the exporter's Action Filter on fills the list with the actions.
    on_export_action_filter_changed(types.SimpleNamespace(export_action_filter=True), bpy.context)
    scene = bpy.data.scenes[0]
    bpy.data.actions.remove(bpy.data.actions["Probe"])
    deleted = [item for item in scene.gltf_action_filter if item.action is None]
    if len(deleted) != 1:
        raise ProbeError(f"{len(deleted)} filter items lost their action, not 1")
    item = deleted[0]
    cls = bpy.types.SCENE_UL_gltf2_filter_action
    ui_list = StandIn(cls)
    for key, value in (
        ("filter_name", "o"),
        ("use_filter_invert", False),
        ("use_filter_sort_alpha", True),
        ("bitflag_filter_item", 1 << 30),
    ):
        setattr(ui_list, key, value)
    cls.draw_item(ui_list, bpy.context, StubLayout(), scene, item, 0, scene, "gltf_action_filter_active", 0)
    cls.filter_items(ui_list, bpy.context, scene, "gltf_action_filter")
    return "drawn"


VARIANT_OPERATORS = (
    "SCENE_OT_gltf2_variant_slot_add",
    "SCENE_OT_gltf2_material_to_variant",
    "SCENE_OT_gltf2_remove_material_variant",
)


def non_mesh_variant() -> dict:
    reset()
    gltf()
    bpy.context.preferences.addons["io_scene_gltf2"].preferences.KHR_materials_variants_ui = True
    curve = bpy.data.curves.new("Probe", "CURVE")
    curve.materials.append(bpy.data.materials.new("Probe"))
    obj = bpy.data.objects.new("Probe", curve)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    from io_scene_gltf2.blender.com import gltf2_blender_ui

    outcome = {}
    for name in VARIANT_OPERATORS:
        cls = getattr(gltf2_blender_ui, name)
        if cls.poll(bpy.context):
            cls.execute(StandIn(cls), bpy.context)
            outcome[name] = "ran"
        else:
            outcome[name] = "rejected"
    return outcome


def non_camera_scene_camera() -> str:
    reset()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    scene.render.resolution_x = 48
    scene.render.resolution_y = 36
    scene.render.resolution_percentage = 100
    scene.render.use_freestyle = True
    bpy.context.view_layer.freestyle_settings.mode = "EDITOR"
    camera = scene.camera
    empty = bpy.data.objects.new("Probe", None)
    empty.matrix_world = camera.matrix_world
    scene.collection.objects.link(empty)
    scene.camera = empty
    modules = bpy.utils.system_resource("SCRIPTS", path="freestyle/modules")
    if modules not in sys.path:
        sys.path.append(modules)
    import parameter_editor

    errors: list[str] = []
    calls: list[str] = []
    process = parameter_editor.process

    def recording_process(*args, **kwargs):
        calls.append("process")
        try:
            return process(*args, **kwargs)
        except Exception:
            errors.append(traceback.format_exc())
            raise

    parameter_editor.process = recording_process
    try:
        bpy.ops.render.render()
    finally:
        parameter_editor.process = process
    if errors:
        raise ProbeError("parameter_editor.process() raised:\n" + errors[0])
    if not calls:
        raise ProbeError("the render did not run parameter_editor.process()")
    return "rendered"


def check_modules(results: dict) -> None:
    check(results, "deleted-filter-action: SCENE_UL_gltf2_filter_action.draw_item", deleted_filter_action)
    check(results, "non-mesh-variant: glTF variant operators", non_mesh_variant)
    check(results, "non-camera-scene-camera: parameter_editor.process", non_camera_scene_camera)


def main() -> None:
    (out,) = script_args()
    results: dict = {}
    check_no_brush(results)
    check_pinned(results)
    check_editors(results)
    check_modules(results)
    write_results(out, results)


if __name__ == "__main__":
    main()
