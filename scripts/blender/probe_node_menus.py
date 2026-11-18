"""Draw every node-add and node-swap menu on a stub layout (run by scripts/probe_node_menus.py, #138).

Usage (inside Blender):
  blender --background --factory-startup --python probe_node_menus.py -- <output json>

Background Blender has no node editor, so each menu ``bl_ui`` registers from ``node_add_menu*.py`` (every
``generate_menu`` class, which mixes ``AddNodeMenu`` / ``SwapNodeMenu`` with a template such as the texture ones) is
drawn by calling its ``draw`` with:

- a ``self`` that reads the registered class and has a recording ``layout``;
- a context whose ``space_data`` is a node editor showing a node tree of the menu's kind, in each variant the menus
  check (geometry modifier / tool, shader object / light / world / line style under EEVEE and Cycles, compositor
  scene / sequencer, texture); every other member comes from ``bpy.context``.

A menu whose own ``poll`` rejects a variant is not drawn there. The layout records each operator, menu and asset
entry. An operator must exist and its properties may only be set when the operator has them; a menu must be
registered. A draw fails when it raises or breaks one of these. The JSON maps each ``<module>:<menu> [<variant>]`` to
its result (``ok``, ``poll``, the entries drawn or the error); the driver reads it.
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
import traceback
import types

import bpy

MODULES = (
    "node_add_menu",
    "node_add_menu_geometry",
    "node_add_menu_shader",
    "node_add_menu_compositor",
    "node_add_menu_texture",
)

# Per module: the node tree type and the space variants its menus read.
VARIANTS = {
    "node_add_menu": ("GeometryNodeTree", [{"node_tree_sub_type": "MODIFIER"}]),
    "node_add_menu_geometry": (
        "GeometryNodeTree",
        [{"node_tree_sub_type": "MODIFIER"}, {"node_tree_sub_type": "TOOL"}],
    ),
    "node_add_menu_shader": (
        "ShaderNodeTree",
        [
            {"shader_type": shader_type, "id_from": id_from, "engine": engine}
            for engine in ("BLENDER_EEVEE", "CYCLES")
            for shader_type, id_from in (("OBJECT", None), ("OBJECT", "LIGHT"), ("WORLD", None), ("LINESTYLE", None))
        ],
    ),
    "node_add_menu_compositor": (
        "CompositorNodeTree",
        [{"node_tree_sub_type": "SCENE"}, {"node_tree_sub_type": "SEQUENCER"}],
    ),
    "node_add_menu_texture": ("TextureNodeTree", [{}]),
}


class ProbeError(Exception):
    pass


class StubProperties:
    """An operator's properties: only the operator's own properties can be read or set."""

    def __init__(self, idname: str, names: set[str]) -> None:
        object.__setattr__(self, "_idname", idname)
        object.__setattr__(self, "_names", names)
        object.__setattr__(self, "_values", {})

    def _check(self, name: str) -> None:
        if name not in self._names:
            raise AttributeError(f"operator {self._idname!r} has no property {name!r}")

    def __getattr__(self, name: str):
        self._check(name)
        if name not in self._values:
            self._values[name] = StubCollection() if name == "settings" else None
        return self._values[name]

    def __setattr__(self, name: str, value) -> None:
        self._check(name)
        self._values[name] = value


class StubCollection:
    def __init__(self) -> None:
        self.items: list[types.SimpleNamespace] = []

    def add(self) -> types.SimpleNamespace:
        self.items.append(types.SimpleNamespace(name="", value=""))
        return self.items[-1]


def operator_properties(idname: str) -> set[str]:
    module, _, name = idname.partition(".")
    op = getattr(getattr(bpy.ops, module), name)
    try:
        rna = op.get_rna_type()
    except Exception:
        raise ProbeError(f"unknown operator {idname!r}") from None
    return {prop.identifier for prop in rna.properties if prop.identifier != "rna_type"}


class StubLayout:
    """Records what a menu draws; sub-layouts (column, row, ...) record into the same list."""

    def __init__(self, entries: list) -> None:
        self._entries = entries

    def operator(self, idname, *, text=None, **_kwargs):
        props = StubProperties(idname, operator_properties(idname))
        self._entries.append(["operator", idname, text, props])
        return props

    def menu(self, name, **_kwargs):
        if not isinstance(getattr(bpy.types, name, None), type):
            raise ProbeError(f"unknown menu {name!r}")
        self._entries.append(["menu", name])

    def menu_contents(self, name):
        self._entries.append(["menu_contents", name])

    def template_node_asset_menu_items(self, *, catalog_path, operator="ADD"):
        self._entries.append(["assets", catalog_path, operator])

    def separator(self, **_kwargs):
        pass

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: StubLayout(self._entries)


class MenuSelf:
    """Stands in for the menu instance Blender passes to ``draw``."""

    def __init__(self, cls: type, layout: StubLayout) -> None:
        object.__setattr__(self, "_cls", cls)
        object.__setattr__(self, "layout", layout)

    def __getattr__(self, name: str):
        value = getattr(self._cls, name)
        if isinstance(inspect.getattr_static(self._cls, name), types.FunctionType):
            return types.MethodType(value, self)
        return value


class Context:
    def __init__(self, space: types.SimpleNamespace, engine: str | None) -> None:
        self.space_data = space
        self.engine = engine or bpy.context.engine

    def __getattr__(self, name: str):
        return getattr(bpy.context, name)


def node_trees(tree_type: str) -> bpy.types.NodeTree:
    """The edited tree, plus a second group of the same type for the group menus to list."""
    tree = bpy.data.node_groups.new(f"Probe {tree_type}", tree_type)
    bpy.data.node_groups.new(f"Probe group {tree_type}", tree_type)
    return tree


def light_object() -> bpy.types.Object:
    return bpy.data.objects.new("Probe light", bpy.data.lights.new("Probe light", "POINT"))


def entry_json(entry: list) -> list:
    if entry[0] != "operator":
        return entry
    props = entry[3]._values
    return entry[:3] + [
        {
            k: repr(v) if not isinstance(v, StubCollection) else [vars(i) for i in v.items]
            for k, v in sorted(props.items())
        }
    ]


def draw(cls: type, variant: dict, tree: bpy.types.NodeTree, light: bpy.types.Object) -> dict:
    space = types.SimpleNamespace(
        type="NODE_EDITOR",
        tree_type=tree.bl_idname,
        edit_tree=tree,
        node_tree=tree,
        shader_type=variant.get("shader_type", "OBJECT"),
        node_tree_sub_type=variant.get("node_tree_sub_type", "SCENE"),
        id_from=light if variant.get("id_from") == "LIGHT" else None,
    )
    context = Context(space, variant.get("engine"))
    if not cls.poll(context):
        return {"ok": True, "poll": False}
    entries: list = []
    cls.draw(MenuSelf(cls, StubLayout(entries)), context)
    return {"ok": True, "poll": True, "entries": [entry_json(e) for e in entries]}


def main() -> None:
    out = sys.argv[sys.argv.index("--") + 1]
    light = light_object()
    results: dict = {}
    for module_name in MODULES:
        module = importlib.import_module(f"bl_ui.{module_name}")
        tree_type, variants = VARIANTS[module_name]
        tree = node_trees(tree_type)
        for module_cls in module.classes:
            cls = getattr(bpy.types, module_cls.bl_idname)
            for variant in variants:
                label = ", ".join(f"{k}={v}" for k, v in variant.items() if v is not None)
                key = f"{module_name}:{cls.bl_idname}" + (f" [{label}]" if label else "")
                try:
                    if cls is not module_cls:
                        raise ProbeError(f"{module_cls.bl_idname} is not registered")
                    results[key] = draw(cls, variant, tree, light)
                except Exception:
                    results[key] = {"ok": False, "error": traceback.format_exc()}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)


main()
