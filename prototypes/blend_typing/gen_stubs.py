"""PROTOTYPE, throwaway. Approach C: turn a blend manifest (approach B) into an overlay stub with `Literal` keys.

Usage: python3 -I gen_stubs.py FILE.blend-manifest.toml [STUBS/bpy/types/__init__.pyi] > OUT.pyi

The stub declares `data`, a `BlendData` whose `objects`, `materials` and `node_groups` know the file's names: `data.objects["Cube"]`
is an `Object` whose `data` is a `Mesh`, `.get("Cube")` is not `None`, and a material's `node_tree.nodes["Principled
BSDF"].inputs["Base Color"]` is a `NodeSocketColor`. Any other key falls back to the stub's own types. A script opts in
by importing `data` from the stub under `TYPE_CHECKING` (stock ty needs no change).
"""

import keyword
import re
import sys
import tomllib


def ident(*parts):
    text = "_".join(re.sub(r"\W", "_", p) for p in parts)
    return "_" + text if keyword.iskeyword(text) or text[:1].isdigit() else "_" + text


def lit(name):
    return "Literal[" + repr(name) + "]"


def collection(out, cls, base, element, items, ids=False):
    """A collection class whose `__getitem__` and `get` know each name, and then repeat the signatures of the
    builtin stubs' `bpy_prop_collection`, so that the class is a valid subclass of its base. A collection of
    data-blocks (`ids`) also takes a `(name, library path)` key."""
    out.append(f"class {cls}({base}):")
    for name, typ in items:
        out += ["    @overload", f"    def __getitem__(self, key: {lit(name)}, /) -> {typ}: ..."]
    out += ["    @overload", f"    def __getitem__(self, key: int, /) -> {element}: ...",
            "    @overload", f"    def __getitem__(self, key: str, /) -> {element}: ..."]
    if ids:
        out += ["    @overload", f"    def __getitem__(self, key: tuple[str, str | None], /) -> {element}: ..."]
    out += ["    @overload", f"    def __getitem__(self, key: slice, /) -> list[{element}]: ..."]
    for name, typ in items:
        out += ["    @overload", f"    def get(self, key: {lit(name)}, default: object = None, /) -> {typ}: ..."]
    out += ["    @overload", f"    def get(self, key: str | tuple[str, str | None], /) -> {element} | None: ...",
            "    @overload", f"    def get(self, key: str | tuple[str, str | None], default: _D, /) -> {element} | _D: ..."]
    out.append("")


def main():
    manifest = tomllib.load(open(sys.argv[1], "rb"))
    # The classes the stubs declare: a built-in node's sockets already have a collection class of their own
    # (`_ShaderNodeBsdfPrincipled_inputs`), so the overlay adds sockets only to the other nodes (groups, custom).
    stub_classes = set()
    if len(sys.argv) > 2:
        stub_classes = set(re.findall(r"^class (\w+)", open(sys.argv[2], encoding="utf-8").read(), re.M))
    used = {"Object", "ObjectModifiers", "Modifier", "Material", "BlendData", "BlendDataObjects", "BlendDataMaterials", "BlendDataNodeTrees", "Node",
            "NodeSocket", "NodeTree", "Nodes", "NodeInputs", "NodeOutputs"}
    out = []

    objects = []
    for name, ob in manifest.get("objects", {}).items():
        cls = ident("Object", name)
        modifiers = [(mod_name, mod_class) for mod_name, mod_class in ob.get("modifiers", [])]
        used.update(mod_class for _, mod_class in modifiers)
        collection(out, cls + "_modifiers", "ObjectModifiers", "Modifier", modifiers)
        out.append(f"class {cls}(Object):")
        out += ["    @property", f"    def modifiers(self) -> {cls}_modifiers: ..."]
        if ob.get("data_class"):
            used.add(ob["data_class"])
            # A property: `Object.data` is writable with any `ID | None`, and only its read type is narrower.
            used.add("ID")
            out += ["    @property", f"    def data(self) -> {ob['data_class']}: ...",
                    "    @data.setter", "    def data(self, value: ID | None, /) -> None: ..."]
        # `type` is writable (with any type the stubs allow, which `str` covers); only its read type is narrower.
        out += ["    @property", f"    def type(self) -> {lit(ob['type'])}: ...",
                "    @type.setter", "    def type(self, value: str, /) -> None: ...", ""]
        objects.append((name, cls))
    collection(out, "_Objects", "BlendDataObjects", "Object", objects, ids=True)

    def tree_class(owner, tree, base):
        """The class of a node tree whose `nodes` know each node by name, and each node its sockets."""
        nodes = []
        for node_name, node in tree["nodes"].items():
            ncls = ident("Node", owner, node_name)
            used.add(node["class"])
            body = []
            for side, sockets_base in (("inputs", "NodeInputs"), ("outputs", "NodeOutputs")):
                if f"_{node['class']}_{side}" in stub_classes:
                    # The stubs already know a built-in node's sockets by name, as its declaration has them.
                    continue
                socks = []
                for sock_name, sock_class in node[side]:
                    used.add(sock_class)
                    socks.append((sock_name, sock_class))
                collection(out, ncls + "_" + side, sockets_base, "NodeSocket", socks)
                body += ["    @property", f"    def {side}(self) -> {ncls}_{side}: ..."]
            out.extend([f"class {ncls}({node['class']}):", *(body or ["    ..."]), ""])
            nodes.append((node_name, ncls))
        collection(out, ident("Nodes", owner), "Nodes", "Node", nodes)
        used.add(base)
        tcls = ident("Tree", owner)
        out.extend([f"class {tcls}({base}):", f"    nodes: {ident('Nodes', owner)}", ""])
        return tcls

    materials = []
    for name, mat in manifest.get("materials", {}).items():
        tree = mat.get("node_tree")
        mcls = ident("Material", name)
        if tree:
            tcls = tree_class("Material_" + name, tree, "ShaderNodeTree")
            out += [f"class {mcls}(Material):", f"    node_tree: {tcls}", ""]
        else:
            out += [f"class {mcls}(Material): ...", ""]
        materials.append((name, mcls))
    collection(out, "_Materials", "BlendDataMaterials", "Material", materials, ids=True)

    groups = []
    for name, tree in manifest.get("node_groups", {}).items():
        groups.append((name, tree_class("Group_" + name, tree, tree["class"])))
    collection(out, "_NodeGroups", "BlendDataNodeTrees", "NodeTree", groups, ids=True)

    out += ["class _BlendData(BlendData):",
            "    objects: _Objects",
            "    materials: _Materials",
            "    node_groups: _NodeGroups", "",
            "data: _BlendData", ""]
    header = [
        f'"""PROTOTYPE overlay stub for {manifest["file"]} (Blender {manifest["blender_version"]}), '
        'generated by prototypes/blend_typing/gen_stubs.py."""', "",
        "from typing import Literal, TypeVar, overload", "",
        "from bpy.types import " + ", ".join(sorted(used)), "",
        '_D = TypeVar("_D")', "",
    ]
    sys.stdout.write("\n".join(header + out))


if __name__ == "__main__":
    main()
