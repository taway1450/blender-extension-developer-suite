# /// script
# requires-python = ">=3.12"
# ///
"""Write the generated feature-test addons and the import roots in ``tests/typecheck/ty.toml``.

Each module in ``scripts/feature_generators/`` belongs to the feature of the same name and returns the files of
``tests/typecheck/features/<feature>/generated/``: addons that cover every variant of a feature and their
combinations, which would be tedious to write by hand. The generated files are committed; ``--check`` fails
when they (or the roots in ty.toml) are out of date, without writing anything.

ty has no glob patterns for ``environment.root``, so the root list (one entry per directory that holds addons)
is written here too, between the ``generated roots`` comments in ty.toml.

Usage:
  uv run scripts/generate_features.py           # write
  uv run scripts/generate_features.py --check   # compare only
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import shutil
import sys
from pathlib import Path

from _common import TYPECHECK_TESTS_DIR, StepError, log, main_wrapper
from _features import FEATURES_DIR, GENERATED, all_addons, import_roots

GENERATORS_DIR = Path(__file__).resolve().parent / "feature_generators"
TY_TOML = TYPECHECK_TESTS_DIR / "ty.toml"
ROOTS_BEGIN = "# BEGIN generated roots (scripts/generate_features.py)"
ROOTS_END = "# END generated roots"


def generated_files() -> dict[Path, str]:
    """Every generated file by its path, from all generator modules."""
    sys.path.insert(0, str(GENERATORS_DIR.parent))
    files: dict[Path, str] = {}
    for info in sorted(pkgutil.iter_modules([str(GENERATORS_DIR)]), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"feature_generators.{info.name}")
        if not (FEATURES_DIR / info.name).is_dir():
            raise StepError(f"Generator {info.name} has no feature directory {FEATURES_DIR / info.name}")
        base = FEATURES_DIR / info.name / GENERATED
        for rel, text in module.generate().items():
            files[base / rel] = text
    return files


def existing_generated() -> set[Path]:
    return {p for p in FEATURES_DIR.glob(f"*/{GENERATED}/**/*") if p.is_file() and "__pycache__" not in p.parts}


def roots_block(roots: list[str]) -> str:
    entries = "".join(f'    "{r}",\n' for r in roots)
    return f"{ROOTS_BEGIN}\nroot = [\n{entries}]\n{ROOTS_END}"


def updated_ty_toml(roots: list[str]) -> str:
    text = TY_TOML.read_text(encoding="utf-8")
    start, end = text.find(ROOTS_BEGIN), text.find(ROOTS_END)
    if start < 0 or end < 0:
        raise StepError(f"{TY_TOML} has no '{ROOTS_BEGIN}' ... '{ROOTS_END}' block")
    return text[:start] + roots_block(roots) + text[end + len(ROOTS_END):]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Fail if the generated files are out of date")
    args = parser.parse_args()

    files = generated_files()
    stale = existing_generated() - set(files)
    changed = [p for p, text in files.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]

    if args.check:
        # The roots depend on which addons exist, so compare them as they will be after writing.
        missing = [p for p in files if not p.is_file()]
        roots_ok = not missing and TY_TOML.read_text(encoding="utf-8") == updated_ty_toml(import_roots(all_addons()))
        for path in sorted(changed):
            print(f"    out of date: {path.relative_to(TYPECHECK_TESTS_DIR).as_posix()}", flush=True)
        for path in sorted(stale):
            print(f"    stale: {path.relative_to(TYPECHECK_TESTS_DIR).as_posix()}", flush=True)
        if not roots_ok:
            print(f"    out of date: roots in {TY_TOML.relative_to(TYPECHECK_TESTS_DIR).as_posix()}", flush=True)
        if changed or stale or not roots_ok:
            log("Generated feature tests are out of date; run `mise run features:generate`")
            return 1
        log(f"{len(files)} generated files and the ty.toml roots are up to date")
        return 0

    for path in sorted(stale):
        path.unlink()
    for directory in sorted({p.parent for p in stale}, key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    for path in changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(files[path], encoding="utf-8", newline="\n")
    for pycache in FEATURES_DIR.glob(f"*/{GENERATED}/**/__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    TY_TOML.write_text(updated_ty_toml(import_roots(all_addons())), encoding="utf-8", newline="\n")
    log(f"Wrote {len(changed)} of {len(files)} generated files, removed {len(stale)} stale ones, updated {TY_TOML.name}")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
