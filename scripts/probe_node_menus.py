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

import json
from collections import defaultdict

from _common import REPO_ROOT, StepError, log, main_wrapper
from _probe import failed_checks, probe_dir, probe_parser, run_probe
from generate_stubs import find_blender

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_node_menus.py"


def changed_menus(previous: dict, results: dict) -> list[str]:
    """The draws (``<module>:<menu> [<variant>]``) whose result differs between two runs, or that only one has."""
    return sorted(key for key in previous.keys() | results.keys() if previous.get(key) != results.get(key))


def draws_by_menu(results: dict) -> dict[str, list[dict]]:
    """Each menu's draw results over the variants, by ``<module>:<menu>`` (the draw's key without its variant)."""
    menus = defaultdict(list)
    for key, result in results.items():
        menus[key.partition(" [")[0]].append(result)
    return menus


def menu_problems(results: dict) -> list[str]:
    """The draws that failed, and the menus whose ``poll`` rejects every variant."""
    problems = failed_checks(results)
    problems += [
        f"{menu} is drawn in no variant (its poll rejects them all)"
        for menu, draws in sorted(draws_by_menu(results).items())
        if not any(r.get("poll") for r in draws)
    ]
    return problems


def main() -> int:
    args = probe_parser(__doc__).parse_args()
    blender = find_blender(args.version, args.blender)
    out = probe_dir("node-menu-probe", args.version)
    result_path = out / "node_menus.json"
    previous_path = out / "node_menus.previous.json"
    if result_path.exists():
        result_path.replace(previous_path)

    results, _ = run_probe(blender, PROBE, result_path)
    drawn = [r for r in results.values() if r.get("poll")]
    entries = sum(len(r["entries"]) for r in drawn)
    log(f"Node menus: {len(draws_by_menu(results))} menus, {len(drawn)} draws over the variants, {entries} entries")
    if previous_path.exists():
        changed = changed_menus(json.loads(previous_path.read_text(encoding="utf-8")), results)
        log(f"Since the previous run: {len(changed)} draws changed" + "".join(f"\n  {key}" for key in changed))
    problems = menu_problems(results)
    if problems:
        raise StepError("node menu probe failed:\n" + "\n".join(problems))
    log("every node-add and node-swap menu drew")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
