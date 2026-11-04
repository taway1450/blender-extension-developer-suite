"""Import, register and unregister feature-test addons inside Blender (run by scripts/check_load.py).

Usage (inside Blender):
  blender --background --factory-startup --python load_feature_addons.py -- <json file with the addons> <output json>

The input is a list of {"name", "root", "module", "register"}; each addon is imported as the top-level module
``module`` from ``root`` and its ``register()`` and ``unregister()`` are called. The output records per addon
whether that worked and the error otherwise.
"""

from __future__ import annotations

import importlib
import json
import sys
import traceback


def load(addon: dict) -> dict:
    if addon["root"] not in sys.path:
        sys.path.insert(0, addon["root"])
    result = {"name": addon["name"], "module": addon["module"]}
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
    result.update(stage="done", error=None)
    return result


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    with open(argv[0], encoding="utf-8") as f:
        addons = json.load(f)
    results = [load(a) for a in addons]
    with open(argv[1], "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)


main()
