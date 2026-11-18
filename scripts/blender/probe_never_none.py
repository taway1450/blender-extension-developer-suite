"""Probe which RNA pointers and function returns Blender leaves None (run by scripts/probe_never_none.py, #109).

Usage (inside Blender):
  blender --background --factory-startup --python probe_never_none.py -- synthetic <output json> <work dir>
  blender --background --factory-startup --python probe_never_none.py -- files <output json> <file list> [<skip list>]

``synthetic`` builds the edge states in factory startup (new data, copies, saved and reloaded files, appended data,
invalid arguments, every node tree type and ID type) and records each candidate's value there. ``files`` opens every
.blend in the list (written as it goes, so the driver can resume after a crash) and records each pointer candidate on
the data it holds. Each record is {"member", "state", "none", "total", "note"}: how many of ``total`` reads were None.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _recorder import script_args

RECORDS: list[dict] = []


def record(member: str, state: str, none: int, total: int, note: str = "") -> None:
    RECORDS.append({"member": member, "state": state, "none": none, "total": total, "note": note})


def count(member: str, state: str, values, note: str = "") -> None:
    values = list(values)
    record(member, state, sum(v is None for v in values), len(values), note)


def outcome(fn) -> str:
    """ "value", "None" or "raises <Error>" for calling ``fn``."""
    try:
        return "None" if fn() is None else "value"
    except Exception as e:
        return f"raises {type(e).__name__}: {str(e).strip().splitlines()[0][:120] if str(e).strip() else ''}"


def call(member: str, state: str, fn, note: str = "") -> str:
    result = outcome(fn)
    record(member, state, int(result == "None"), int(not result.startswith("raises")), f"{result}; {note}".strip("; "))
    return result


# -----------------------------------------------------------------------------
# Pointer candidates on whatever data is loaded


def node_trees():
    seen = set()
    for tree in bpy.data.node_groups:
        seen.add(tree.as_pointer())
        yield tree
    for collection in (
        bpy.data.materials,
        bpy.data.worlds,
        bpy.data.lights,
        bpy.data.scenes,
        bpy.data.linestyles,
        bpy.data.textures,
    ):
        for id_ in collection:
            tree = getattr(id_, "node_tree", None) or getattr(id_, "compositing_node_group", None)
            if tree is not None and tree.as_pointer() not in seen:
                seen.add(tree.as_pointer())
                yield tree


def probe_loaded(state: str) -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs
    for name in ("active", "default", "addon", "user"):
        count(f"KeyConfigurations.{name}", state, [getattr(kc, name)])
    count(
        "WindowManager.xr_session_state", state, [wm.xr_session_state], "XrSessionState.viewfinder is read through it"
    )

    count("Material.node_tree", state, [m.node_tree for m in bpy.data.materials])
    count("World.node_tree", state, [w.node_tree for w in bpy.data.worlds])

    links, internal = [], []
    for tree in node_trees():
        links.extend(tree.links)
        for node in tree.nodes:
            internal.extend(node.internal_links)
    for end in ("from_node", "to_node", "from_socket", "to_socket"):
        count(f"NodeLink.{end}", state, [getattr(link, end) for link in links])
    for end in ("from_socket", "to_socket"):
        count(f"NodeInternalLink.{end}", state, [getattr(link, end) for link in internal])

    count("Bone.color", state, [b.color for a in bpy.data.armatures for b in a.bones])
    count(
        "PoseBone.color",
        state,
        [b.color for o in bpy.data.objects if o.type == "ARMATURE" and o.pose for b in o.pose.bones],
    )

    clips = list(bpy.data.movieclips)
    count("MovieTracking.reconstruction", state, [c.tracking.reconstruction for c in clips])
    count("MovieTrackingObjects.active", state, [c.tracking.objects.active for c in clips])
    count("MovieTrackingObject.reconstruction", state, [o.reconstruction for c in clips for o in c.tracking.objects])

    active, inactive = [], []
    for screen in bpy.data.screens:
        for area in screen.areas:
            for i, space in enumerate(area.spaces):
                if space.type == "VIEW_3D":
                    (active if i == 0 else inactive).append(space.region_3d)
    count("SpaceView3D.region_3d", state + ", active space", active)
    count("SpaceView3D.region_3d", state + ", inactive space", inactive)

    scene = bpy.context.scene
    if scene is None:
        return
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for name in ("scene", "scene_eval", "view_layer", "view_layer_eval"):
        count(f"Depsgraph.{name}", state, [getattr(depsgraph, name)])
    objects, instance_objects, parents = [], [], []
    for i, inst in enumerate(depsgraph.object_instances):
        if i >= 5000:
            break
        objects.append(inst.object)
        instance_objects.append(inst.instance_object)
        parents.append(inst.parent)
    count("DepsgraphObjectInstance.object", state, objects)
    count("DepsgraphObjectInstance.instance_object", state, instance_objects, "control: None when not an instance")
    count("DepsgraphObjectInstance.parent", state, parents, "control: None when not an instance")


# -----------------------------------------------------------------------------
# Synthetic edge states in factory startup


def png(path: str) -> str:
    image = bpy.data.images.new("probe_frame", 8, 8)
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)
    return path


def probe_node_tree_new() -> None:
    func = bpy.types.BlendDataNodeTrees.bl_rna.functions["new"]
    items = [item.identifier for item in func.parameters["type"].enum_items]
    record("BlendDataNodeTrees.new", "enum items at definition", 0, 0, ", ".join(items))
    for idname in ("ShaderNodeTree", "GeometryNodeTree", "CompositorNodeTree", "TextureNodeTree"):
        call("BlendDataNodeTrees.new", f"type={idname!r}", lambda: bpy.data.node_groups.new("probe", idname))
    call("BlendDataNodeTrees.new", "type='NoSuchTree'", lambda: bpy.data.node_groups.new("probe", "NoSuchTree"))
    call("BlendDataNodeTrees.new", "type=''", lambda: bpy.data.node_groups.new("probe", ""))

    class ProbeCustomTree(bpy.types.NodeTree):
        bl_idname = "ProbeCustomTree"
        bl_label = "Probe"
        bl_icon = "NODETREE"

    bpy.utils.register_class(ProbeCustomTree)
    call(
        "BlendDataNodeTrees.new", "custom registered type", lambda: bpy.data.node_groups.new("probe", "ProbeCustomTree")
    )
    bpy.utils.unregister_class(ProbeCustomTree)
    call(
        "BlendDataNodeTrees.new",
        "custom type after unregister",
        lambda: bpy.data.node_groups.new("probe", "ProbeCustomTree"),
    )


def new_id(collection: str):
    """A new ID in ``bpy.data.<collection>`` from the simplest call that makes one, or None if there is none."""
    data = getattr(bpy.data, collection)
    attempts = {
        "objects": lambda: data.new("probe", None),
        "node_groups": lambda: data.new("probe", "ShaderNodeTree"),
        "images": lambda: data.new("probe", 4, 4),
        "curves": lambda: data.new("probe", "CURVE"),
        "lights": lambda: data.new("probe", "POINT"),
        "textures": lambda: data.new("probe", "IMAGE"),
        "brushes": lambda: data.new("probe", "SCULPT"),
        "lightprobes": lambda: data.new("probe", "SPHERE"),
        "fonts": lambda: data.load(os.path.join(bpy.utils.system_resource("DATAFILES"), "fonts", "DejaVuSans.woff2")),
        "libraries": lambda: None,
        "screens": lambda: None,
        "window_managers": lambda: None,
        "workspaces": lambda: None,
        "movieclips": lambda: None,
        "sounds": lambda: None,
        "batch_remove": lambda: None,
    }
    if collection in attempts:
        return attempts[collection]()
    if hasattr(data, "new"):
        try:
            return data.new("probe")
        except TypeError:
            return None
    return None


def blend_data_collections() -> list[str]:
    return [
        p.identifier
        for p in bpy.types.BlendData.bl_rna.properties
        if p.type == "COLLECTION" and p.identifier not in {"rna_type"}
    ]


def probe_animation_data_create() -> None:
    nullable, never = [], []
    for collection in blend_data_collections():
        ids = list(getattr(bpy.data, collection))
        try:
            made = new_id(collection)
        except Exception:
            made = None
        if made is not None:
            ids.insert(0, made)
        if not ids:
            continue
        id_ = ids[0]
        result = outcome(id_.animation_data_create)
        type_name = type(id_).__name__
        (nullable if result == "None" else never).append(type_name)
        record("ID.animation_data_create", f"on {type_name} (bpy.data.{collection})", int(result == "None"), 1, result)
    record(
        "ID.animation_data_create", "summary: None for", len(nullable), len(nullable) + len(never), ", ".join(nullable)
    )


def probe_id_properties_ui() -> None:
    obj = bpy.data.objects.new("probe_props", None)
    obj["prop"] = 1.0
    obj["text"] = "x"
    call("bpy_struct.id_properties_ui", "ID with float key", lambda: obj.id_properties_ui("prop"))
    call("bpy_struct.id_properties_ui", "ID with string key", lambda: obj.id_properties_ui("text"))
    call("bpy_struct.id_properties_ui", "ID, missing key", lambda: obj.id_properties_ui("missing"))
    fresh = bpy.data.objects.new("probe_props_empty", None)
    call("bpy_struct.id_properties_ui", "ID with no properties at all", lambda: fresh.id_properties_ui("missing"))
    obj["group"] = {"a": 1}
    call("bpy_struct.id_properties_ui", "group-valued key", lambda: obj.id_properties_ui("group"))
    scene = bpy.context.scene
    call(
        "bpy_struct.id_properties_ui",
        "non-ID struct without idprops (SceneRender)",
        lambda: scene.render.id_properties_ui("x"),
    )
    arm = bpy.data.armatures.new("probe_arm")
    arm_obj = bpy.data.objects.new("probe_arm", arm)
    scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    arm.edit_bones.new("Bone").tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode="POSE")
    pbone = arm_obj.pose.bones["Bone"]
    pbone["p"] = 2
    call("bpy_struct.id_properties_ui", "PoseBone with key", lambda: pbone.id_properties_ui("p"))
    call("bpy_struct.id_properties_ui", "PoseBone, missing key", lambda: pbone.id_properties_ui("q"))
    bpy.ops.object.mode_set(mode="EDIT")
    ebone = arm.edit_bones["Bone"]
    count("EditBone.color", "edit mode, new bone", [ebone.color])
    bpy.ops.object.mode_set(mode="OBJECT")
    count("Bone.color", "new armature", [b.color for b in arm.bones])
    count("PoseBone.color", "new armature", [b.color for b in arm_obj.pose.bones])


def probe_material_world(work: str) -> None:
    mat = bpy.data.materials.new("probe_mat")
    count("Material.node_tree", "bpy.data.materials.new()", [mat.node_tree])
    count("Material.node_tree", "Material.copy()", [mat.copy().node_tree])
    gp = bpy.data.materials.new("probe_gp")
    bpy.data.materials.create_gpencil_data(gp)
    count("Material.node_tree", "materials.create_gpencil_data()", [gp.node_tree])
    count("Material.node_tree", "after setting deprecated use_nodes = False", [_set_use_nodes(mat)])
    world = bpy.data.worlds.new("probe_world")
    count("World.node_tree", "bpy.data.worlds.new()", [world.node_tree])
    count("World.node_tree", "World.copy()", [world.copy().node_tree])
    count("Material.node_tree", "bpy.data.materials (factory startup)", [m.node_tree for m in bpy.data.materials])
    count("World.node_tree", "bpy.data.worlds (factory startup)", [w.node_tree for w in bpy.data.worlds])
    obj = bpy.data.objects.new("probe_mat_holder", bpy.data.meshes.new("probe_mesh"))
    obj.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(obj)
    for m in bpy.data.materials:
        m.use_fake_user = True
    for w in bpy.data.worlds:
        w.use_fake_user = True
    path = os.path.join(work, "probe_saved.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    with bpy.data.libraries.load(path) as (data_from, data_to):
        data_to.materials = [n for n in data_from.materials if n.startswith("probe")]
        data_to.worlds = [n for n in data_from.worlds if n.startswith("probe")]
    count("Material.node_tree", "appended with libraries.load()", [m.node_tree for m in data_to.materials])
    count("World.node_tree", "appended with libraries.load()", [w.node_tree for w in data_to.worlds])
    with bpy.data.libraries.load(path, link=True) as (data_from, data_to):
        data_to.materials = ["probe_mat"]
    count("Material.node_tree", "linked with libraries.load(link=True)", [m.node_tree for m in data_to.materials])


def _set_use_nodes(mat):
    try:
        mat.use_nodes = False
    except Exception:
        pass
    return mat.node_tree


def probe_tracking(work: str) -> None:
    frame = png(os.path.join(work, "probe_clip_0001.png"))
    clip = bpy.data.movieclips.load(frame)
    tracking = clip.tracking
    count("MovieTracking.reconstruction", "new clip", [tracking.reconstruction])
    count("MovieTrackingObjects.active", "new clip (camera object only)", [tracking.objects.active])
    extra = tracking.objects.new("probe_obj")
    tracking.objects.active = extra
    count("MovieTrackingObjects.active", "second object active", [tracking.objects.active])
    tracking.objects.remove(extra)
    count(
        "MovieTrackingObjects.active",
        "after removing the active object (set through .active)",
        [tracking.objects.active],
        f"index reads {tracking.active_object_index}",
    )
    try:
        tracking.active_object_index = 99
    except Exception as e:
        record("MovieTracking.active_object_index", "set to 99", 0, 0, f"raises {type(e).__name__}")
    count(
        "MovieTrackingObjects.active",
        "after active_object_index = 99",
        [tracking.objects.active],
        f"index reads {tracking.active_object_index}, {len(tracking.objects)} objects",
    )
    tracking.active_object_index = 0
    extra = tracking.objects.new("probe_obj2")
    tracking.active_object_index = 1
    tracking.objects.remove(extra)
    count(
        "MovieTrackingObjects.active",
        "index 1 active, then that object removed",
        [tracking.objects.active],
        f"index reads {tracking.active_object_index}, {len(tracking.objects)} objects",
    )
    call("MovieTrackingObjects.remove", "the camera object", lambda: tracking.objects.remove(tracking.objects[0]))
    count("MovieTracking.reconstruction", "after trying to remove the camera object", [tracking.reconstruction])
    count("MovieTrackingObject.reconstruction", "new clip", [o.reconstruction for o in tracking.objects])


def probe_region_3d() -> None:
    """A View3D space made in background: switch a non-3D area to VIEW_3D (it becomes the active space), then
    back (it stays as an inactive space of the area)."""
    values_active, values_inactive, notes = [], [], []
    for screen in bpy.data.screens:
        for area in screen.areas:
            old = area.type
            if old == "VIEW_3D":
                continue
            with bpy.context.temp_override(screen=screen, area=area):
                area.type = "VIEW_3D"
            space = area.spaces.active
            notes.append(f"{old}->{space.type}")
            if space.type == "VIEW_3D":
                values_active.append(space.region_3d)
            with bpy.context.temp_override(screen=screen, area=area):
                area.type = old
            values_inactive.extend(s.region_3d for s in area.spaces if s.type == "VIEW_3D" and s != area.spaces.active)
    count("SpaceView3D.region_3d", "area switched to VIEW_3D in background", values_active, ", ".join(notes[:3]))
    count("SpaceView3D.region_3d", "inactive View3D after switching back", values_inactive)


def probe_depsgraph_updates() -> None:
    seen = []

    def handler(scene, depsgraph):
        seen.extend(update.id for update in depsgraph.updates)
        seen_scene.append(depsgraph.scene)

    seen_scene: list = []
    bpy.app.handlers.depsgraph_update_post.append(handler)
    obj = bpy.data.objects.new("probe_update", bpy.data.meshes.new("probe_update"))
    bpy.context.scene.collection.objects.link(obj)
    obj.location.x = 1
    bpy.context.view_layer.update()
    bpy.data.objects.remove(obj)
    bpy.context.view_layer.update()
    bpy.app.handlers.depsgraph_update_post.remove(handler)
    count("DepsgraphUpdate.id", "depsgraph_update_post, add/move/remove an object", seen)
    count("Depsgraph.scene", "depsgraph_update_post", seen_scene)


def probe_returns() -> None:
    mesh = bpy.data.meshes.new("probe_uv")
    results = [outcome(lambda: mesh.uv_layers.new(name=f"uv{i}")) for i in range(10)]
    record("MeshUVLoopLayers.new", "10 calls on one mesh", results.count("None"), len(results), ", ".join(results))

    ball_data = bpy.data.metaballs.new("probe_ball")
    ball_data.elements.new()
    mother = bpy.data.objects.new("Ball", ball_data)
    child = bpy.data.objects.new("Ball.001", ball_data)
    for o in (mother, child):
        bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    call("Object.to_mesh", "mother metaball", lambda: mother.evaluated_get(depsgraph).to_mesh())
    call("Object.to_mesh", "non-mother metaball", lambda: child.evaluated_get(depsgraph).to_mesh())
    empty = bpy.data.objects.new("probe_empty", None)
    call("Object.to_mesh", "empty", lambda: empty.to_mesh())
    call("BlendDataMeshes.new_from_object", "empty", lambda: bpy.data.meshes.new_from_object(empty))
    call(
        "BlendDataMeshes.new_from_object",
        "non-mother metaball",
        lambda: bpy.data.meshes.new_from_object(child.evaluated_get(depsgraph)),
    )
    call("BlendDataObjects.new", "data is a Material", lambda: bpy.data.objects.new("x", bpy.data.materials.new("m")))
    call("ObjectModifiers.new", "SUBSURF on an empty", lambda: empty.modifiers.new("m", "SUBSURF"))
    call(
        "ObjectModifiers.new",
        "SUBSURF on a mesh",
        lambda: bpy.data.objects.new("o", bpy.data.meshes.new("m")).modifiers.new("m", "SUBSURF"),
    )
    prefs = bpy.context.preferences.filepaths.asset_libraries
    call("AssetLibraryCollection.new", "local, empty directory", lambda: prefs.new(name="probe", directory=""))
    call(
        "AssetLibraryCollection.new", "extension_id without remote_url", lambda: prefs.new(name="p2", extension_id="x")
    )


def synthetic(output: str, work: str) -> None:
    steps = [
        ("factory startup", lambda: probe_loaded("factory startup, background")),
        ("node_groups.new", probe_node_tree_new),
        ("animation_data_create", probe_animation_data_create),
        ("id_properties_ui", probe_id_properties_ui),
        ("material/world", lambda: probe_material_world(work)),
        ("tracking", lambda: probe_tracking(work)),
        ("region_3d", probe_region_3d),
        ("depsgraph updates", probe_depsgraph_updates),
        ("returns", probe_returns),
        ("after loads", lambda: probe_loaded("factory startup + synthetic data, background")),
        ("read_homefile", lambda: (bpy.ops.wm.read_homefile(), probe_loaded("after wm.read_homefile()"))),
        (
            "read_factory_settings empty",
            lambda: (
                bpy.ops.wm.read_factory_settings(use_empty=True),
                probe_loaded("after read_factory_settings(use_empty=True)"),
            ),
        ),
        (
            "read_homefile empty",
            lambda: (bpy.ops.wm.read_homefile(use_empty=True), probe_loaded("after read_homefile(use_empty=True)")),
        ),
    ]
    for name, step in steps:
        try:
            step()
        except Exception:
            record("probe step failed", name, 0, 0, traceback.format_exc()[-500:])
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(RECORDS, fh, indent=1)


def files(output: str, file_list: str, skip_list: str | None) -> None:
    with open(file_list, encoding="utf-8") as fh:
        paths = [line.strip() for line in fh if line.strip()]
    skip = set()
    if skip_list and os.path.exists(skip_list):
        with open(skip_list, encoding="utf-8") as fh:
            skip = {line.strip() for line in fh}
    done = set()
    if os.path.exists(output):
        with open(output, encoding="utf-8") as fh:
            for line in fh:
                done.add(json.loads(line)["file"])
    progress = output + ".current"
    for path in paths:
        if path in skip or path in done:
            continue
        with open(progress, "w", encoding="utf-8") as fh:
            fh.write(path)
        RECORDS.clear()
        try:
            bpy.ops.wm.open_mainfile(filepath=path, load_ui=True)
            version = ".".join(map(str, bpy.data.version))
            probe_loaded(f"loaded file (saved by {version})")
            error = None
        except Exception as e:
            error = f"{type(e).__name__}: {str(e)[:200]}"
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"file": path, "error": error, "records": RECORDS}) + "\n")
    if os.path.exists(progress):
        os.remove(progress)


def main() -> None:
    argv = script_args()
    if argv[0] == "synthetic":
        synthetic(argv[1], argv[2])
    else:
        files(argv[1], argv[2], argv[3] if len(argv) > 3 else None)


main()
