# /// script
# requires-python = ">=3.12"
# ///
"""Draw the bl_ui panels and menus that raised in a rare state, in that state, in background Blender (#148).

Runs ``scripts/blender/probe_ui_draw.py`` in Blender (background, factory startup). Each check calls a panel's or
menu's ``draw`` on a stub layout (which rejects None RNA pointers as Blender's does) with a context in one of the
states the spec #146 review found: a paint mode without a brush, a pinned Properties editor (particle settings,
object data, an armature), a node group interface without an active item, a workspace without a sequencer scene, a
sequencer scene without a sequence editor, no open project. Fails when a draw raises or a poll rejects its state.
Blender's output goes to ``.cache/ui-draw-probe/<version>/blender.log``, the results to ``result.json``.

Usage:
  uv run scripts/probe_ui_draw.py main
"""

from __future__ import annotations

from _common import REPO_ROOT, StepError, log, main_wrapper
from _probe import failed_checks, probe_dir, probe_parser, run_probe
from generate_stubs import find_blender

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_ui_draw.py"


def main() -> int:
    args = probe_parser(__doc__).parse_args()
    blender = find_blender(args.version, args.blender)
    out = probe_dir("ui-draw-probe", args.version)
    results, _ = run_probe(blender, PROBE, out / "result.json")
    for name, result in results.items():
        log(f"{'ok  ' if result['ok'] else 'FAIL'} {name}" + (f": {result['value']}" if result["ok"] else ""))
    problems = failed_checks(results)
    if problems:
        raise StepError(f"{len(problems)} of {len(results)} draws failed:\n" + "\n".join(problems))
    log(f"all {len(results)} draws passed")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
