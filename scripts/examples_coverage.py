# /// script
# requires-python = ">=3.12"
# ///
"""Write the coverage tables of the example add-ons into ``examples/addons/README.md``.

A ``# demo: <id>`` comment line in an example add-on names what the statement below it shows. ``<id>`` is a
feature directory of ``tests/typecheck/features/``, a ``blender-*`` rule, or ``later/<topic>`` for a behaviour that
does not work yet. What a tag claims is checked against the results ``check:addons`` recorded for the builtin
stubs of Blender main (``examples/expected/builtin/main.txt``):

- a rule's statement must be reported under that rule (or carry its ``# ty: ignore[<rule>]`` marker);
- a feature's statement must not fail (a ``blender-*`` warning on it is fine);
- a ``later/`` statement must fail: when it starts to pass, the topic works and its tag becomes a feature tag.

``examples/addons/coverage.toml`` describes the ``later/`` topics (``[later.<topic>]`` with ``description``, and
``untagged`` with the reason when no line of an add-on can show the topic) and lists the features and rules the
examples leave to the feature tests (``[exempt]``, with the reason). Every feature directory and every rule of
``crates/ty/docs/rules.md`` needs a tag or an exemption.

``--check`` writes nothing and fails when a tag does not hold, something is not covered or the tables are out of
date.

Usage:
  uv run scripts/examples_coverage.py           # write
  uv run scripts/examples_coverage.py --check   # compare only
"""

from __future__ import annotations

import argparse
import ast
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from _baseline import EXAMPLES, EXAMPLES_EXPECTED_DIR, SEPARATOR, Kind
from _common import EXAMPLE_ADDONS_DIR, REPO_ROOT, TY_SUBMODULE, StepError, log, main_wrapper
from _features import FEATURES_DIR, feature_names
from _markers import EXPECTED_ERROR, line_keys

README = EXAMPLE_ADDONS_DIR / "README.md"
COVERAGE_TOML = EXAMPLE_ADDONS_DIR / "coverage.toml"
RULES_MD = TY_SUBMODULE / "ruff-blender" / "crates" / "ty" / "docs" / "rules.md"
# The results the statuses are read from: the builtin stubs know the most, and main is the newest Blender.
REFERENCE_GENERATOR = "builtin"
REFERENCE_VERSION = "main"

TABLES_BEGIN = "<!-- BEGIN coverage (mise run examples:coverage) -->"
TABLES_END = "<!-- END coverage -->"
TAG = re.compile(r"^\s*#\s*demo:\s*(?P<id>\S+)\s*$")
RULE_HEADING = re.compile(r"^## `(?P<rule>blender-[a-z-]+)`$")
RULE_LEVEL = re.compile(r"^Default level: .*?<code>(?P<level>[a-z]+)</code>")
RULE_PREFIX = "blender-"
LATER_PREFIX = "later/"
UNUSED_MARKER = "unused-ignore-comment"


@dataclass(frozen=True)
class Demo:
    """A ``# demo:`` tag and the statement below it."""

    id: str
    path: str  # relative to examples/addons, with forward slashes
    line: int  # of the tag, 1-based
    keys: tuple[str, ...]  # the line keys of the statement (see ``_markers.line_keys``)
    markers: frozenset[tuple[str, str]]  # (line key, rule) of the statement's ``# ty: ignore[...]`` markers

    @property
    def where(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class Config:
    """``coverage.toml``."""

    later: dict[str, dict[str, str]] = field(default_factory=dict)  # topic -> description, source, untagged
    exempt: dict[str, str] = field(default_factory=dict)  # feature or rule -> reason


def statement_lines(tree: ast.Module, first: int) -> range:
    """The lines of the statement that starts on line ``first``: all of a simple statement, the header of a
    compound one (with its decorators). A line that starts no statement stands for itself."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        decorators = getattr(node, "decorator_list", [])
        start = min([node.lineno, *(d.lineno for d in decorators)])
        if start != first:
            continue
        body = getattr(node, "body", None)
        end = body[0].lineno - 1 if isinstance(body, list) and body else node.end_lineno or node.lineno
        return range(first, max(first, end) + 1)
    return range(first, first + 1)


def file_demos(path: str, text: str, tag_pattern: re.Pattern[str] = TAG) -> list[Demo]:
    """The tags of one file. A tag is a comment line of its own; comment lines may follow it before the statement.
    ``tag_pattern`` matches a tag line and names its ``id`` (the catalog's Gap tags use another one)."""
    lines = text.splitlines()
    keys = line_keys(lines)
    tree = ast.parse(text)
    demos = []
    for index, line in enumerate(lines):
        tag = tag_pattern.match(line)
        if not tag:
            continue
        first = index + 1
        while first < len(lines) and (not lines[first].strip() or lines[first].lstrip().startswith("#")):
            first += 1
        if first >= len(lines):
            raise StepError(f"{path}:{index + 1}: the tag `{tag['id']}` has no statement below it")
        covered = statement_lines(tree, first + 1)
        markers = set()
        for number in covered:
            marker = EXPECTED_ERROR.search(lines[number - 1])
            for rule in marker["rules"].split(",") if marker else []:
                markers.add((keys[number - 1], rule.strip()))
        demos.append(Demo(tag["id"], path, index + 1, tuple(keys[n - 1] for n in covered), frozenset(markers)))
    return demos


def all_demos(root: Path) -> list[Demo]:
    """The tags of every Python file below ``root``, in path order."""
    demos = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" not in path.parts:
            demos += file_demos(path.relative_to(root).as_posix(), path.read_text(encoding="utf-8"))
    return demos


def read_config(path: Path) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return Config(data.get("later", {}), data.get("exempt", {}))


def read_rules(path: Path, heading_pattern: re.Pattern[str] = RULE_HEADING) -> dict[str, str]:
    """Every ``blender-*`` rule of the rule reference (or every rule whose heading ``heading_pattern`` matches) with
    its default level."""
    rules: dict[str, str] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = heading_pattern.match(line)
        if heading:
            current = heading["rule"]
            rules[current] = ""
        elif line.startswith("## "):
            current = None  # another rule: its level is not the last matched rule's
        elif current and not rules[current] and (level := RULE_LEVEL.match(line)):
            rules[current] = level["level"]
    return rules


def read_results(path: Path, kind: Kind = EXAMPLES) -> set[tuple[str, str, str]]:
    """The recorded results as (path, rule, line key)."""
    results = set()
    for entry in kind.read(path):
        file, rule, key = entry.split(SEPARATOR, 2)
        results.add((file, rule, key))
    return results


def reported(demo: Demo, results: set[tuple[str, str, str]]) -> set[str]:
    """The rules recorded on the statement of ``demo``."""
    return {rule for path, rule, key in results if path == demo.path and key in demo.keys}


def shows_rule(demo: Demo, results: set[tuple[str, str, str]]) -> bool:
    """Whether the statement is reported under the rule ``demo`` names: recorded so, or hidden by a marker in use."""
    if demo.id in reported(demo, results):
        return True
    return any(rule == demo.id and (demo.path, UNUSED_MARKER, key) not in results for key, rule in demo.markers)


def fails(demo: Demo, results: set[tuple[str, str, str]]) -> bool:
    """Whether something other than a ``blender-*`` finding is recorded on the statement."""
    return any(not rule.startswith(RULE_PREFIX) for rule in reported(demo, results))


@dataclass
class Coverage:
    features: dict[str, list[Demo]]
    rules: dict[str, list[Demo]]
    later: dict[str, list[Demo]]
    levels: dict[str, str]
    config: Config
    problems: list[str]


def coverage(
    demos: list[Demo],
    features: list[str],
    levels: dict[str, str],
    config: Config,
    results: set[tuple[str, str, str]],
) -> Coverage:
    """Sort the tags by what they name and list what does not hold."""
    by_id: dict[str, list[Demo]] = {}
    for demo in demos:
        by_id.setdefault(demo.id, []).append(demo)
    problems = []

    for name, found in by_id.items():
        if name.startswith(LATER_PREFIX):
            topic = name.removeprefix(LATER_PREFIX)
            if topic not in config.later:
                problems.append(f"{found[0].where}: `{name}` has no [later.{topic}] entry in coverage.toml")
            elif not any(reported(demo, results) for demo in found):
                problems.append(f"{found[0].where}: `{name}` works now: tag it as the feature it belongs to")
        elif name in levels:
            problems += [
                f"{demo.where}: the statement is not reported as `{name}`"
                for demo in found
                if not shows_rule(demo, results)
            ]
        elif name in features:
            problems += [
                f"{demo.where}: the statement fails ({', '.join(sorted(reported(demo, results)))}): tag it `later/...`"
                for demo in found
                if fails(demo, results)
            ]
        else:
            problems.append(f"{found[0].where}: `{name}` is no feature, rule or `later/` topic")

    for name in [*features, *levels]:
        tagged, exempt = name in by_id, name in config.exempt
        if tagged and exempt:
            problems.append(f"`{name}` is exempt in coverage.toml but has a tag ({by_id[name][0].where})")
        elif not tagged and not exempt:
            problems.append(f"`{name}` has no `# demo: {name}` tag and no [exempt] entry in coverage.toml")
    problems += [
        f"[exempt] `{name}` in coverage.toml is no feature or rule"
        for name in config.exempt
        if name not in features and name not in levels
    ]
    for topic, entry in config.later.items():
        tagged = LATER_PREFIX + topic in by_id
        if "description" not in entry:
            problems.append(f"[later.{topic}] in coverage.toml has no description")
        if tagged and "untagged" in entry:
            problems.append(f"[later.{topic}] in coverage.toml says `untagged` but has a tag")
        elif not tagged and "untagged" not in entry:
            problems.append(f"[later.{topic}] in coverage.toml has no `# demo: later/{topic}` tag and no `untagged`")

    return Coverage(
        {name: by_id.get(name, []) for name in features},
        {name: by_id.get(name, []) for name in levels},
        {topic: by_id.get(LATER_PREFIX + topic, []) for topic in config.later},
        levels,
        config,
        problems,
    )


def links(demos: list[Demo]) -> str:
    """The files the tags are in, as links relative to the README."""
    return ", ".join(f"[{path}]({path})" for path in dict.fromkeys(demo.path for demo in demos))


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    """A Markdown table. A ``|`` inside a cell would end the cell, so it is escaped."""
    lines = [header, ["---"] * len(header), *rows]
    return [f"| {' | '.join(cell.replace('|', chr(92) + '|') for cell in row)} |" for row in lines]


def tables(result: Coverage) -> str:
    """The Markdown between the two marker lines of the README."""
    features_dir = Path("..") / ".." / FEATURES_DIR.relative_to(REPO_ROOT)
    feature_rows = [
        [
            f"[`{name}`]({(features_dir / name / 'README.md').as_posix()})",
            links(found) if found else f"feature tests only: {result.config.exempt.get(name, '')}",
        ]
        for name, found in result.features.items()
    ]
    rule_rows = [
        [
            f"`{name}`",
            result.levels[name],
            links(found) if found else f"feature tests only: {result.config.exempt.get(name, '')}",
        ]
        for name, found in result.rules.items()
    ]
    later_rows = [
        [
            f"`{topic}`",
            entry.get("description", ""),
            entry.get("source", ""),
            links(result.later[topic]) if result.later[topic] else f"no line shows it: {entry.get('untagged', '')}",
        ]
        for topic, entry in sorted(result.config.later.items())
    ]
    lines = [
        TABLES_BEGIN,
        "",
        "### Features",
        "",
        *table(["Feature", "Shown in"], feature_rows),
        "",
        "### Rules",
        "",
        *table(["Rule", "Default level", "Reported in"], rule_rows),
        "",
        "### Not working yet",
        "",
        *table(["Topic (`later/...`)", "What is missing", "Source", "Shown in"], later_rows),
        "",
        TABLES_END,
    ]
    return "\n".join(lines)


def updated_readme(text: str, block: str) -> str:
    """``text`` with the part between the marker lines replaced by ``block``."""
    start, end = text.find(TABLES_BEGIN), text.find(TABLES_END)
    if start < 0 or end < start:
        raise StepError(f"{README} has no `{TABLES_BEGIN}` ... `{TABLES_END}` lines")
    return text[:start] + block + text[end + len(TABLES_END) :]


def current() -> Coverage:
    """The coverage of the example add-ons as they are in the repository."""
    if not RULES_MD.is_file():
        raise StepError(f"{RULES_MD} is missing: check out the ty-blender submodule with its ruff-blender submodule")
    results = read_results(EXAMPLES.file(REFERENCE_GENERATOR, REFERENCE_VERSION, EXAMPLES_EXPECTED_DIR))
    config = read_config(COVERAGE_TOML)
    return coverage(all_demos(EXAMPLE_ADDONS_DIR), feature_names(), read_rules(RULES_MD), config, results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Fail if a tag does not hold or the tables are stale")
    args = parser.parse_args()

    result = current()
    for problem in result.problems:
        print(f"    {problem}", flush=True)
    text = README.read_text(encoding="utf-8")
    updated = updated_readme(text, tables(result))
    shown = sum(1 for found in [*result.features.values(), *result.rules.values()] if found)
    summary = f"{shown} features and rules shown, {len(result.config.exempt)} exempt, {len(result.later)} later topics"

    if args.check:
        if updated != text:
            log(
                f"The tables in {README.relative_to(REPO_ROOT).as_posix()} are out of date; run `mise run examples:coverage`"
            )
        if result.problems or updated != text:
            return 1
        log(f"Up to date: {summary}")
        return 0

    if updated != text:
        README.write_text(updated, encoding="utf-8")
        log(f"Wrote {README.relative_to(REPO_ROOT).as_posix()}")
    log(summary)
    return 1 if result.problems else 0


if __name__ == "__main__":
    main_wrapper(main)
