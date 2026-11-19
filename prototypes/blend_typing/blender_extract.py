"""PROTOTYPE, throwaway. Approach G (B inside Blender): read a .blend with Blender itself and write the typing facts as a TOML manifest.

Runs inside Blender (``mise run probe:blend-typing``, which calls it in background Blender):

    blender --background --factory-startup --python blender_extract.py -- OUT_DIR FILE.blend [FILE.blend ...]

For each file it opens the file (``bpy.ops.wm.open_mainfile``, so Blender's versioning runs) and writes
``OUT_DIR/<file>.blend-manifest.toml`` in the schema of ``extract_manifest.py`` (approach B), so the overlay
generator (approach C) reads either. The difference to B: the facts are those of the *loaded* file, as a script sees
them: renamed sockets, new idnames, rebuilt node declarations and Blender's own RNA classes, not DNA struct names.
"""

import os
import sys
import time

import bpy

# The `bpy.data` collections B records, by the two-letter ID code B keys them on (the TOML key is the collection).
COLLECTIONS = [
    "objects", "meshes", "materials", "scenes", "cameras", "lights", "armatures", "node_groups", "images",
    "collections", "worlds", "actions", "curves", "textures", "libraries", "hair_curves", "pointclouds",
    "grease_pencils", "volumes", "lattices", "shape_keys",
]


def q(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def socket_pairs(sockets):
    # `bl_idname` is the RNA class of a built-in socket (`NodeSocketColor`), and the registered class of a custom one.
    return "[" + ", ".join(f"[{q(s.name)}, {q(s.bl_idname)}]" for s in sockets) + "]"


def write_nodes(out, prefix, tree):
    for node in tree.nodes:
        out += ["", f"[{prefix}.nodes.{q(node.name)}]", f"class = {q(node.bl_idname)}"]
        out.append(f"inputs = {socket_pairs(node.inputs)}")
        out.append(f"outputs = {socket_pairs(node.outputs)}")


def manifest(path, seconds):
    out = [
        "# PROTOTYPE blend manifest, written by prototypes/blend_typing/blender_extract.py (Blender, loaded state)",
        f"file = {q(os.path.basename(path))}",
        # The version that saved the file, as B records it (major * 100 + minor), and the one that loaded it.
        f"blender_version = {bpy.data.version[0] * 100 + bpy.data.version[1]}",
        f"loaded_by = {bpy.app.version[0] * 100 + bpy.app.version[1]}",
        f"parse_seconds = {seconds:.4f}",
        "",
        "[ids]",
    ]
    for name in COLLECTIONS:
        collection = getattr(bpy.data, name, None)
        if collection:
            # Linked IDs are keyed by (name, library path) in Python; the manifest keeps the name as B does.
            out.append(f"{name} = [{', '.join(q(item.name) for item in collection)}]")
    for ob in bpy.data.objects:
        out += ["", f"[objects.{q(ob.name)}]", f"type = {q(ob.type)}"]
        if ob.data is not None:
            out += [f"data_class = {q(type(ob.data).__name__)}", f"data = {q(ob.data.name)}"]
        out.append("modifiers = [" + ", ".join(f"[{q(m.name)}, {q(type(m).__name__)}]" for m in ob.modifiers) + "]")
    for mat in bpy.data.materials:
        if mat.node_tree is not None:
            write_nodes(out, f"materials.{q(mat.name)}.node_tree", mat.node_tree)
    for tree in bpy.data.node_groups:
        out += ["", f"[node_groups.{q(tree.name)}]", f"class = {q(tree.bl_idname)}"]
        write_nodes(out, f"node_groups.{q(tree.name)}", tree)
    return "\n".join(out) + "\n"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out_dir, paths = argv[0], argv[1:]
    os.makedirs(out_dir, exist_ok=True)
    for path in paths:
        start = time.perf_counter()
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
        text = manifest(path, time.perf_counter() - start)
        target = os.path.join(out_dir, os.path.basename(path) + "-manifest.toml")
        with open(target, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"blend-typing: wrote {target}")


main()
