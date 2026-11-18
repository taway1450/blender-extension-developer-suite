# /// script
# requires-python = ">=3.12"
# ///
"""Draw every node-add and node-swap menu on a stub layout in background Blender (#138).

Runs ``scripts/blender/probe_node_menus.py``, which calls the ``draw`` of each menu ``bl_ui`` registers from
``node_add_menu*.py`` (every ``generate_menu`` class, the texture templates included) in a stand-in node editor, once
per space variant the menus read. A draw fails when it raises or uses an unknown operator, operator property or menu;
a menu fails when its own ``poll`` rejects every variant.

The results go to ``.cache/node-menu-probe/<version>/node_menus.json``. The previous run's file is kept as
``node_menus.previous.json`` and the menus whose entries changed since are listed, so a run before and after a change
to the menus shows whether it changed what they draw.

Usage:
  uv run scripts/probe_node_menus.py main
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _common import CACHE_DIR, REPO_ROOT, StepError, log, main_wrapper, validate_version
from generate_stubs import find_blender

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_node_menus.py"
BLENDER_ARGS = ["--background", "--factory-startup", "-noaudio", "--python-exit-code", "1"]


def changed_menus(previous: dict, results: dict) -> list[str]:
    return sorted(key for key in previous.keys() | results.keys() if previous.get(key) != results.get(key))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_version, help="Blender version (X.Y) or build name (e.g. main)")
    parser.add_argument("--blender", type=Path, help="Blender binary (or its directory) to use")
    args = parser.parse_args()

    blender = find_blender(args.version, args.blender)
    out = CACHE_DIR / "node-menu-probe" / args.version
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "node_menus.json"
    previous_path = out / "node_menus.previous.json"
    if result_path.exists():
        result_path.replace(previous_path)

    command = [str(c) for c in [blender, *BLENDER_ARGS, "--python", PROBE, "--", result_path]]
    proc = subprocess.run(command, capture_output=True, text=True)
    (out / "blender.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode or not result_path.exists():
        raise StepError(f"node menu probe failed with exit code {proc.returncode} (see {out / 'blender.log'})")

    results = json.loads(result_path.read_text(encoding="utf-8"))
    drawn = [key for key, r in results.items() if r.get("poll")]
    menus = {key.partition(" [")[0] for key in results}
    entries = sum(len(results[key]["entries"]) for key in drawn)
    log(f"Node menus: {len(menus)} menus, {len(drawn)} draws over the variants, {entries} entries")
    if previous_path.exists():
        changed = changed_menus(json.loads(previous_path.read_text(encoding="utf-8")), results)
        log(f"Since the previous run: {len(changed)} draws changed" + "".join(f"\n  {key}" for key in changed))
    problems = [f"{key} failed:\n{r['error']}" for key, r in results.items() if not r["ok"]]
    problems += [f"{menu} is drawn in no variant (its poll rejects them all)" for menu in sorted(menus)
                 if not any(results[key].get("poll") for key in results if key.partition(" [")[0] == menu)]
    if problems:
        raise StepError("node menu probe failed:\n" + "\n".join(problems))
    log("every node-add and node-swap menu drew")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
