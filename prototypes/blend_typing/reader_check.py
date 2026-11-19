"""PROTOTYPE, throwaway. Approach A: the checker reads the .blend itself, at check time, and types the add-on's lookups.

Usage: python3 -I reader_check.py ADDON_DIR

What a reader inside ty would do, in Python so that it runs today. No manifest is written and no stub is generated:

1. **Binding.** The add-on's manifest declares the files its code runs against (``[tool.blender] blend-files =
   ["assets.blend"]``); without a declaration, every ``.blend`` in the add-on's folder.
2. **Reading.** Each file is read with ``blendread`` (no Blender) and the same facts as approach B are taken from it.
   Several files merge as section 5 of the research says: a name must be in every file, and its type is kept only
   where every file agrees.
3. **Typing.** Every ``reveal_type(expr)`` in the add-on's modules is resolved syntactically: ``bpy.data`` (or a
   module-level ``data`` bound to it) and its ``objects``, ``materials`` and ``node_groups`` with literal keys,
   ``[...]`` and ``.get(...)``, then ``.data``, ``.type``, ``.modifiers[...]``, ``.node_tree``, ``.nodes[...]``,
   ``.inputs[...]`` and ``.outputs[...]``, through simple aliases (``rock = data.objects["Rock"]``). It prints the
   type a checker would give, and where the type comes from.

A key no bound file holds keeps the stubs' type (a script may create the data), as the overlay of approach C does.
"""

import ast
import os
import sys
import time
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blendread  # noqa: E402
import extract_manifest  # noqa: E402

STUB_TYPES = {"objects": "Object", "materials": "Material", "node_groups": "NodeTree"}


def bound_files(addon):
    manifest = os.path.join(addon, "blender_manifest.toml")
    if os.path.exists(manifest):
        with open(manifest, "rb") as f:
            declared = tomllib.load(f).get("tool", {}).get("blender", {}).get("blend-files")
        if declared:
            return [os.path.join(addon, name) for name in declared]
    return sorted(os.path.join(addon, name) for name in os.listdir(addon) if name.endswith(".blend"))


def read_facts(path):
    """The facts of one file, as nested dicts keyed like the manifest of approach B."""
    blend = blendread.open_blend(path)
    _ids, objects, materials, groups = extract_manifest.extract(blend)
    return {
        "objects": objects,
        "materials": {name: mat["node_tree"] for name, mat in materials.items()},
        "node_groups": {name: tree for name, tree in groups.items() if tree},
        "version": blend.version,
    }


def merge(facts):
    """The facts every file agrees on: names in all files, a value only where all files give the same one."""
    first, rest = facts[0], facts[1:]

    def agree(values):
        return values[0] if all(v == values[0] for v in values[1:]) else None

    merged = {}
    for collection in STUB_TYPES:
        names = set(first[collection]).intersection(*(f[collection] for f in rest))
        merged[collection] = {name: agree([f[collection][name] for f in facts]) for name in names}
    return merged


class Resolver:
    """A type for an expression: (description, facts) where facts is the fact dict behind it, or None."""

    def __init__(self, facts):
        self.facts = facts
        self.aliases = {}

    def literal(self, node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    def resolve(self, node):
        if isinstance(node, ast.Name):
            if node.id in self.aliases:
                return self.aliases[node.id]
            return ("BlendData", "root") if node.id == "data" else None
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "bpy" and node.attr == "data":
                return ("BlendData", "root")
            base = self.resolve(node.value)
            return self.attribute(base, node.attr) if base else None
        if isinstance(node, ast.Subscript):
            base = self.resolve(node.value)
            key = self.literal(node.slice)
            return self.item(base, key, get=False) if base else None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            base = self.resolve(node.func.value)
            key = self.literal(node.args[0]) if node.args else None
            return self.item(base, key, get=True) if base else None
        return None

    def attribute(self, base, name):
        kind, fact = base
        if fact == "root" and name in STUB_TYPES:
            return (f"collection:{name}", self.facts[name])
        if kind.startswith("Object") and isinstance(fact, dict):
            if name == "data":
                return (fact.get("data_class") or "None", None)
            if name == "type":
                return (f"Literal['{fact['type']}']", None)
            if name == "modifiers":
                return ("collection:modifiers", dict(fact["modifiers"]))
        if kind == "Material" and name == "node_tree" and fact:
            return (fact["class"], fact)
        if name == "nodes" and isinstance(fact, dict) and "nodes" in fact:
            return ("collection:nodes", fact["nodes"])
        if name in ("inputs", "outputs") and isinstance(fact, dict) and name in fact:
            return (f"collection:{name}", dict(fact[name]))
        return None

    def item(self, base, key, get):
        kind, fact = base
        if not kind.startswith("collection:") or key is None:
            return None
        collection = kind.split(":", 1)[1]
        value = fact.get(key) if isinstance(fact, dict) else None
        if value is None:
            return None  # unknown key: the stubs' type stays
        if collection == "objects":
            return (f"Object (type {value['type']!r}, data {value.get('data_class')})", value)
        if collection == "materials":
            return ("Material", value)
        if collection == "node_groups":
            return (value["class"], value)
        if collection == "nodes":
            return (value["class"], value)
        return (value, None)  # a modifier or socket: its class name


def check_module(path, facts):
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    results = []
    for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        resolver = Resolver(facts)
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                resolved = resolver.resolve(node.value)
                if resolved:
                    resolver.aliases[node.targets[0].id] = resolved
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "reveal_type":
                resolved = resolver.resolve(node.args[0])
                shown = resolved[0] if resolved and not resolved[0].startswith("collection:") else "(stubs' type)"
                results.append((node.lineno, ast.unparse(node.args[0]), shown))
    return sorted(results)


def main():
    addon = sys.argv[1]
    start = time.perf_counter()
    files = bound_files(addon)
    facts = merge([read_facts(path) for path in files])
    read_seconds = time.perf_counter() - start
    print(f"# approach A: {', '.join(os.path.basename(p) for p in files)} read in {read_seconds * 1000:.0f} ms")
    for root, _dirs, names in os.walk(addon):
        for name in sorted(names):
            if name.endswith(".py"):
                path = os.path.join(root, name)
                for line, expr, shown in check_module(path, facts):
                    print(f"{os.path.relpath(path, addon)}:{line}: {expr} -> {shown}")


if __name__ == "__main__":
    main()
