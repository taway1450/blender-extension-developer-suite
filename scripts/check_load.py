# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Load every feature-test addon in Blender: import it, call register() and unregister().

The feature tests state runtime types, so their addons have to be real addons that Blender accepts. An addon that
is broken on purpose (for example one that registers classes in the wrong order, for ``registration_checks``)
says so in ``<addon>/_expected/runtime.toml``::

    register = "fails"   # or "ok" (the default)
    reason = "PropertyGroup registered after the class that points to it"
    # For an addon folder that is not itself a package (a workspace with several addons): the packages to load,
    # relative to the addon folder.
    packages = ["addons/ws_alpha", "addons/ws_beta"]
    # For a folder that is not an add-on at all (a library other add-ons import): do not load it.
    load = false
    # For an addon that fails: text the error must contain, so that it fails for the stated reason.
    error = "to have 2 args, found 1"

    # Probes, evaluated in Blender after register(): a Python expression with bpy, addon (the addon module) and the
    # helpers healthy(cls) and can_add_node(tree_idname, node_idname) of scripts/blender/load_feature_addons.py,
    # and the value it must give ("raises" if it must raise).
    [[probe]]
    code = "healthy(addon.MY_PT_parent)"
    expect = false
    reason = "registering MY_PT_child detached the parent's Python class"

The task fails when an addon does not do what it says.

Usage:
  uv run scripts/check_load.py main
  uv run scripts/check_load.py 5.4 registration_checks
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from _common import CACHE_DIR, REPO_ROOT, StepError, log, main_wrapper, validate_version
from _features import Addon, select
from generate_stubs import find_blender, run_blender_script

LOADER = REPO_ROOT / "scripts" / "blender" / "load_feature_addons.py"
RESULTS_DIR = CACHE_DIR / "typecheck-results"


def runtime_spec(addon: Addon) -> dict:
    path = addon.path / "_expected" / "runtime.toml" if addon.path.is_dir() else None
    return tomllib.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}


def packages(addon: Addon, spec: dict) -> list[Path]:
    if addon.path.is_file() or (addon.path / "__init__.py").is_file():
        return [addon.path]
    listed = [addon.path / p for p in spec.get("packages", [])]
    if not listed:
        raise StepError(f"{addon.rel} is not a package; list its packages in _expected/runtime.toml")
    return listed


def probe_problems(probes: list[dict], results: list) -> list[str]:
    """The probes whose result is not the expected one (an addon that failed to register has no results)."""
    problems = []
    for probe, got in zip(probes, results):
        expect = probe["expect"]
        holds = isinstance(got, str) and got.startswith("raises") if expect == "raises" else got == expect
        if not holds:
            problems.append(f"probe {probe['code']} gave {got!r}, expected {expect!r} ({probe.get('reason', '')})")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_version, help="Blender version (X.Y) or build name (e.g. main)")
    parser.add_argument("features", nargs="*", help="Features or addons (feature/addon) (default: all)")
    parser.add_argument("--blender", type=Path, help="Blender binary (or its directory) to use")
    args = parser.parse_args()

    entries, expectations = [], {}
    for addon in select(args.features):
        spec = runtime_spec(addon)
        if spec.get("load", True) is False:
            continue
        for package in packages(addon, spec):
            name = f"{addon.feature}/{package.relative_to(addon.path.parent).as_posix()}"
            entries.append(
                {"name": name, "root": str(package.parent), "module": package.stem, "probes": spec.get("probe", [])}
            )
            expectations[name] = spec

    blender = find_blender(args.version, args.blender)
    work = RESULTS_DIR / args.version
    work.mkdir(parents=True, exist_ok=True)
    (work / "load-input.json").write_text(json.dumps(entries, indent=1), encoding="utf-8")
    log(f"Loading {len(entries)} addons in Blender")
    run_blender_script(blender, LOADER, work / "load-input.json", work / "load.json")

    failures = 0
    for result in json.loads((work / "load.json").read_text(encoding="utf-8")):
        spec = expectations[result["name"]]
        expected, reason = spec.get("register", "ok"), spec.get("reason", "")
        ok = result["error"] is None
        problems = probe_problems(spec.get("probe", []), result["probes"])
        if not ok and expected != "ok" and spec.get("error") and spec["error"] not in result["error"]:
            problems.append(
                f"fails in {result['stage']}, but not with {spec['error']!r}:\n            "
                + result["error"].strip().replace("\n", "\n            ")
            )
        if ok == (expected == "ok") and not problems:
            note = "ok" if ok else f"fails as expected in {result['stage']} ({reason})"
            probes = f", {len(result['probes'])} probes hold" if result["probes"] else ""
            print(f"    {result['name']}: {note}{probes}", flush=True)
            continue
        failures += 1
        if ok == (expected == "ok"):
            print(f"    {result['name']}: FAIL:\n        " + "\n        ".join(problems), flush=True)
            continue
        if ok:
            print(f"    {result['name']}: FAIL: loads, but _expected/runtime.toml says it fails ({reason})", flush=True)
        else:
            print(
                f"    {result['name']}: FAIL in {result['stage']}:\n        "
                + result["error"].strip().replace("\n", "\n        "),
                flush=True,
            )
    log(f"{failures} of {len(entries)} addons did not load as expected")
    return 1 if failures else 0


if __name__ == "__main__":
    main_wrapper(main)
