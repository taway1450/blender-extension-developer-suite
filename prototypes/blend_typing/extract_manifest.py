"""PROTOTYPE, throwaway. Approach B: read a .blend without Blender and write the typing facts as a TOML manifest.

Usage: python3 -I extract_manifest.py FILE.blend > FILE.blend-manifest.toml

Facts, cheapest first: the ID names per type; each object's type and its data's type and name; its modifiers; each
material's (embedded) node tree with its nodes' classes and their input and output sockets' classes. Names come from
the file as stored: Blender's load-time versioning (renamed sockets, ...) is not applied, so the manifest records the
file's Blender version for a reader to judge.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blendread  # noqa: E402

# `ID.name`'s two-letter prefix: the `bpy.data` collection and the `bpy.types` class (DNA_ID_enums.h).
ID_CODES = {
    "OB": ("objects", "Object"), "ME": ("meshes", "Mesh"), "MA": ("materials", "Material"),
    "SC": ("scenes", "Scene"), "CA": ("cameras", "Camera"), "LA": ("lights", "Light"),
    "AR": ("armatures", "Armature"), "NT": ("node_groups", "NodeTree"), "IM": ("images", "Image"),
    "GR": ("collections", "Collection"), "WO": ("worlds", "World"), "AC": ("actions", "Action"),
    "CU": ("curves", "Curve"), "TE": ("textures", "Texture"), "LI": ("libraries", "Library"),
    "CV": ("hair_curves", "Curves"), "PT": ("pointclouds", "PointCloud"), "GP": ("grease_pencils", "GreasePencil"),
    "VO": ("volumes", "Volume"), "LT": ("lattices", "Lattice"), "KE": ("shape_keys", "Key"),
}
# `Object.type` (DNA_object_types.h) and the `bpy.types` class its data has.
OBJECT_TYPES = {
    0: ("EMPTY", None), 1: ("MESH", "Mesh"), 2: ("CURVE", "Curve"), 3: ("SURFACE", "SurfaceCurve"),
    4: ("FONT", "TextCurve"), 5: ("META", "MetaBall"), 10: ("LIGHT", "Light"), 11: ("CAMERA", "Camera"),
    12: ("SPEAKER", "Speaker"), 13: ("LIGHT_PROBE", "LightProbe"), 22: ("LATTICE", "Lattice"),
    25: ("ARMATURE", "Armature"), 27: ("CURVES", "Curves"), 28: ("POINTCLOUD", "PointCloud"),
    29: ("VOLUME", "Volume"), 30: ("GREASEPENCIL", "GreasePencil"),
}


def id_name(blend, block):
    return blend.read(block[5], "ID", "name")


def sockets(blend, node_block, listbase):
    return [
        (blend.read(s[5], "bNodeSocket", "name"), blend.read(s[5], "bNodeSocket", "idname"))
        for s in blend.listbase(node_block[5], "bNode", listbase, "bNodeSocket")
    ]


def node_tree(blend, tree_ptr):
    tree = blend.by_old.get(tree_ptr)
    if tree is None:
        return None
    nodes = {}
    for node in blend.listbase(tree[5], "bNodeTree", "nodes", "bNode"):
        nodes[blend.read(node[5], "bNode", "name")] = {
            "class": blend.read(node[5], "bNode", "idname"),
            "inputs": sockets(blend, node, "inputs"),
            "outputs": sockets(blend, node, "outputs"),
        }
    return {"class": blend.read(tree[5], "bNodeTree", "idname"), "nodes": nodes}


def extract(blend):
    ids = {}
    objects, materials = {}, {}
    for block in blend.blocks:
        code = block[0].decode(errors="replace")
        if code not in ID_CODES:
            continue
        name = id_name(blend, block)[2:]
        ids.setdefault(code, []).append(name)
        if code == "OB":
            kind, data_class = OBJECT_TYPES.get(blend.read(block[5], "Object", "type"), ("UNKNOWN", None))
            data = blend.by_old.get(blend.read(block[5], "Object", "data"))
            modifiers = [
                # The modifier's DNA struct (`SubsurfModifierData`) names its RNA class (`SubsurfModifier`).
                (blend.read(m[5], "ModifierData", "name"), blend.sname(m).removesuffix("Data"))
                for m in blend.listbase(block[5], "Object", "modifiers", "ModifierData")
            ]
            objects[name] = {
                "type": kind,
                "data_class": data_class,
                "data": id_name(blend, data)[2:] if data else None,
                "modifiers": modifiers,
            }
        elif code == "MA":
            tree = node_tree(blend, blend.read(block[5], "Material", "nodetree"))
            materials[name] = {"node_tree": tree}
    return ids, objects, materials


def q(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_toml(path, blend, ids, objects, materials, seconds):
    out = [
        "# PROTOTYPE blend manifest, written by prototypes/blend_typing/extract_manifest.py",
        f"file = {q(os.path.basename(path))}",
        f"blender_version = {blend.version}",
        f"parse_seconds = {seconds:.4f}",
        "",
        "[ids]",
    ]
    for code, names in sorted(ids.items()):
        out.append(f"{ID_CODES[code][0]} = [{', '.join(q(n) for n in names)}]")
    for name, ob in objects.items():
        out += ["", f"[objects.{q(name)}]", f"type = {q(ob['type'])}"]
        if ob["data_class"]:
            out += [f"data_class = {q(ob['data_class'])}", f"data = {q(ob['data'])}"]
        out.append("modifiers = [" + ", ".join(f"[{q(n)}, {q(c)}]" for n, c in ob["modifiers"]) + "]")
    for name, mat in materials.items():
        tree = mat["node_tree"]
        if tree is None:
            continue
        for node_name, node in tree["nodes"].items():
            out += ["", f"[materials.{q(name)}.node_tree.nodes.{q(node_name)}]", f"class = {q(node['class'])}"]
            for side in ("inputs", "outputs"):
                out.append(f"{side} = [" + ", ".join(f"[{q(n)}, {q(c)}]" for n, c in node[side]) + "]")
    return "\n".join(out) + "\n"


def main():
    path = sys.argv[1]
    start = time.perf_counter()
    blend = blendread.open_blend(path)
    ids, objects, materials = extract(blend)
    seconds = time.perf_counter() - start
    sys.stdout.write(write_toml(path, blend, ids, objects, materials, seconds))


if __name__ == "__main__":
    main()
