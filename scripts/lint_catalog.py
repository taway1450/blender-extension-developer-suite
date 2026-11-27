# /// script
# requires-python = ">=3.12"
# ///
"""Run ruff on the catalog entries that carry a ``[lint]`` table and record what it reports.

Each such entry names a ruff rule and claims whether ruff reports it with the rule turned on: once with stock
settings (``--isolated --extend-select RULE``) and once with the linter profile ``config/ruff/addons.toml``. The
profile run uses a copy of the profile that selects the rule inside its own ``[lint]`` table, so the profile's
``ignore`` and rule settings (pep8-naming's ``ignore-names``) still apply: a rule selected on the command line would
override them. Both runs target the Python of the Blender commit the ``blender`` submodule pins, read from its
``versions.cmake`` (CI fetches that file on demand). Ruff is stock ruff (``uvx ruff@<version ruff-blender is based on>``, see build_ty.py); nothing is built.

The counts go to ``examples/expected/catalog-lint.txt`` with the hash of each entry's code; ``catalog:generate``
judges the ``[lint]`` claims against that file. Without ``--update`` the run compares with the file and fails when a
count changed or a claim does not hold.

Usage:
  uv run scripts/lint_catalog.py                       # every entry with a [lint] table
  uv run scripts/lint_catalog.py tooling --update      # one topic, rewriting its lines
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess

from _catalog import (
    LINT_RECORDED,
    LintResult,
    blender_commit,
    code_hash,
    lint_verdict,
    load_entry,
    read_lint,
    write_lint,
)
from _common import BLENDER_SUBMODULE, CACHE_DIR, CATALOG_DIR, REPO_ROOT, StepError, log, main_wrapper
from _features import catalog_entry_list
from build_ty import stock_command
from generate_stubs import VERSIONS_CMAKE, python_short_version
from run_ruff import LINT_RE, PROFILES_DIR, RUFF_CACHE

PROFILE = PROFILES_DIR / "addons.toml"
PROFILE_COPIES = CACHE_DIR / "ruff-catalog"
LINT_TABLE = re.compile(r"^\[lint\][ \t]*$", re.MULTILINE)


def profile_selecting(profile: str, rule: str) -> str:
    """The profile with ``rule`` selected inside its own ``[lint]`` table."""
    match = LINT_TABLE.search(profile)
    if match is None:
        raise StepError(f"{PROFILE.name} has no [lint] table to select {rule} in")
    return f'{profile[: match.end()]}\nextend-select = ["{rule}"]{profile[match.end() :]}'


def count_findings(output: str, rule: str) -> int:
    """How often ``ruff check --output-format concise`` reported ``rule``."""
    return sum(m["rule"] == rule for m in LINT_RE.finditer(output))


def target_version(versions_cmake: str) -> str:
    """Ruff's ``--target-version`` (``py313``) for the Python a Blender ``versions.cmake`` names."""
    return f"py{python_short_version(versions_cmake).replace('.', '')}"


def pinned_versions_cmake() -> str:
    """The text of ``versions.cmake`` at the Blender commit the ``blender`` submodule pins."""
    commit = blender_commit()
    if commit is None:
        raise StepError("The blender submodule does not have its pinned commit: `git submodule update --init blender`")
    shown = subprocess.run(
        ["git", "-C", str(BLENDER_SUBMODULE), "show", f"{commit}:{VERSIONS_CMAKE}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if shown.returncode:
        raise StepError(f"Could not read {VERSIONS_CMAKE} at {commit[:10]}: {shown.stderr.strip()}")
    return shown.stdout


def ruff_output(ruff: list[str], options: list[str], path: str) -> str:
    cmd = [*ruff, "check", *options, "--no-fix", "--output-format", "concise", "--cache-dir", str(RUFF_CACHE), path]
    result = subprocess.run(cmd, cwd=CATALOG_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode not in (0, 1):  # 1: findings, 2: ruff itself failed
        raise StepError(f"ruff check failed on {path} with exit code {result.returncode}: {result.stderr[-2000:]}")
    return result.stdout


def rule_name(ruff: list[str], rule: str) -> str:
    """The rule's name (``invalid-class-name`` for ``N801``), which its documentation page is named after."""
    result = subprocess.run(
        [*ruff, "rule", rule, "--output-format", "json"], capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise StepError(f"`{rule}` is no ruff rule: {result.stderr.strip()}")
    return json.loads(result.stdout)["name"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "entries", nargs="*", help="Topics or entries (topic/entry) of examples/catalog/ (default: all)"
    )
    parser.add_argument("--update", action="store_true", help=f"Rewrite {LINT_RECORDED.name} instead of comparing")
    args = parser.parse_args()

    ruff = [str(part) for part in stock_command("ruff")]
    target = ["--target-version", target_version(pinned_versions_cmake())]
    recorded = read_lint(LINT_RECORDED.read_text(encoding="utf-8")) if LINT_RECORDED.is_file() else {}
    addons = catalog_entry_list(args.entries)
    entries = [(addon, load_entry(addon)) for addon in addons]
    linted = [(addon, entry) for addon, entry in entries if entry.header.lint.get("rule")]
    log(f"Running ruff ({target[1]}) on {len(linted)} catalog entries with a [lint] table")
    PROFILE_COPIES.mkdir(parents=True, exist_ok=True)
    found: dict[str, LintResult] = {}
    names: dict[str, str] = {}  # rule -> its name, asked of ruff once per rule
    for addon, entry in linted:
        rule = entry.header.lint["rule"]
        copy = PROFILE_COPIES / f"addons-{rule}.toml"
        copy.write_text(profile_selecting(PROFILE.read_text(encoding="utf-8"), rule), encoding="utf-8")
        default = ruff_output(ruff, ["--isolated", *target, "--extend-select", rule], entry.rel)
        profile = ruff_output(ruff, ["--config", str(copy), *target], entry.rel)
        found[entry.rel] = LintResult(
            code_hash(addon),
            rule,
            names.get(rule) or names.setdefault(rule, rule_name(ruff, rule)),
            count_findings(default, rule),
            count_findings(profile, rule),
        )
        log(f"{entry.id}: {rule} default {found[entry.rel].default}, profile {found[entry.rel].profile}")

    # The lines this run owns: its entries', and on a full run every line (so a removed entry's line goes).
    owned = set(recorded) if not args.entries else {addon.rel for addon in addons}
    updated = {path: r for path, r in recorded.items() if path not in owned} | found
    changed = sorted(path for path in set(recorded) | set(updated) if recorded.get(path) != updated.get(path))
    for path in changed:
        print(f"    {path}: recorded {recorded.get(path)}, now {updated.get(path)}", flush=True)
    problems = [p for _, entry in linted for p in lint_verdict(entry, updated, found[entry.rel].hash)]
    for problem in problems:
        print(f"    {problem}", flush=True)
    where = LINT_RECORDED.relative_to(REPO_ROOT).as_posix()
    if args.update:
        LINT_RECORDED.write_text(write_lint(updated), encoding="utf-8", newline="\n")
        log(f"Wrote {where}")
    elif changed:
        log(f"The ruff results differ from {where}; rerun with --update after reviewing them")
        return 1
    else:
        log(f"Matches {where}")
    return 1 if problems else 0


if __name__ == "__main__":
    main_wrapper(main)
