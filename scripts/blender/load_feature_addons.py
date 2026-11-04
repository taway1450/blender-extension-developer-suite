"""Import, register and unregister feature-test addons inside Blender (run by scripts/check_load.py).

Usage (inside Blender):
  blender --background --factory-startup --python load_feature_addons.py -- <json file with the addons> <output json>

The input is a list of {"name", "root", "module", "probes"}; each addon is imported as the top-level module
``module`` from ``root`` and its ``register()`` and ``unregister()`` are called. Between the two, each probe's
``code`` (a Python expression) is evaluated with ``bpy``, ``addon`` (the addon module) and the helpers below as
names; its result, or ``"raises"`` if it raises, is recorded. The output records per addon whether that worked,
the error otherwise, and the probe results.
"""

from __future__ import annotations

import importlib
import json
import sys
import traceback

import bpy


def healthy(cls: type) -> bool:
    """Whether Blender still uses ``cls`` for its RNA type: ``bpy.types.<name>`` gives the class back. After a
    subclass of a registered class is registered, Blender detaches the base's Python class (bpy_rna.cc), and
    bpy.types gives a generated class instead (or raises, for UI lists); Blender no longer calls its callbacks."""
    try:
        return getattr(bpy.types, cls.__name__, None) is cls
    except Exception:
        return False


def can_add_node(tree_idname: str, node_idname: str) -> bool:
    """Whether a node of ``node_idname`` can be added to a new tree of ``tree_idname`` (Node classes are not in
    bpy.types, so this is how a broken or rejected node shows)."""
    tree = bpy.data.node_groups.new("check_load", tree_idname)
    try:
        tree.nodes.new(node_idname)
        return True
    except RuntimeError:
        return False
    finally:
        bpy.data.node_groups.remove(tree)


def probe(module, code: str):
    try:
        value = eval(code, {"bpy": bpy, "addon": module, "healthy": healthy, "can_add_node": can_add_node})
        return value if isinstance(value, (bool, int, float, str, type(None))) else repr(value)
    except Exception as e:
        return f"raises ({type(e).__name__}: {e})"[:300]


def load(addon: dict) -> dict:
    if addon["root"] not in sys.path:
        sys.path.insert(0, addon["root"])
    result = {"name": addon["name"], "module": addon["module"], "probes": []}
    try:
        module = importlib.import_module(addon["module"])
    except Exception:
        result.update(stage="import", error=traceback.format_exc(limit=3))
        return result
    for stage in ("register", "unregister"):
        func = getattr(module, stage, None)
        if func is None:
            result.update(stage=stage, error=f"{addon['module']} has no {stage}()")
            return result
        try:
            func()
        except Exception:
            result.update(stage=stage, error=traceback.format_exc(limit=3))
            return result
        if stage == "register":
            result["probes"] = [probe(module, p["code"]) for p in addon.get("probes", [])]
    result.update(stage="done", error=None)
    return result


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :]
    with open(argv[0], encoding="utf-8") as f:
        addons = json.load(f)
    results = [load(a) for a in addons]
    with open(argv[1], "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)


main()
