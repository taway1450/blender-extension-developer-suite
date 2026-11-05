"""The recorded results in ``tests/typecheck/expected/<generator>/<version>.*`` and the progress table built from them.

Three files per stub generator and Blender version:

- ``<version>.txt``: the ``check:features`` results that are not passes, one entry per line;
- ``<version>.ide.md``: every ``check:ide`` result, one section per marker;
- ``<version>.progress.md``: passes per feature, computed from the other two and the markers in the source.

An entry is named by its file and line key (``_markers.line_keys``), never by line number, so moving code does not
change it. Every entry starts with its path and `` | ``; that is how a partial run finds the entries it owns.

The check tasks hand a run's entries to ``record``, which compares them with the file (or rewrites it with
``--update``), prints what changed and keeps the progress table current.
"""

from __future__ import annotations

import collections
import difflib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from _common import REPO_ROOT, TYPECHECK_TESTS_DIR, log
from _features import Addon, AddonResult, all_addons, feature_names, ide_markers, type_files
from _markers import ASSERT, IdeMarker, TypeMarker

EXPECTED_DIR = TYPECHECK_TESTS_DIR / "expected"
SEPARATOR = " | "


def entry_path(key: str) -> str:
    return key.partition(SEPARATOR)[0]


def type_entry(path: str, rule: str, line_key: str) -> str:
    """A ``check:features`` result: ``path | rule | line key``."""
    return f"{path}{SEPARATOR}{rule}{SEPARATOR}{line_key}"


def type_entries(results: list[AddonResult]) -> dict[str, str]:
    """Everything that is not a pass, one entry per (line, rule), in file and line order, with ty's messages.

    The messages are only shown, never recorded: they change with every type-rendering tweak, while the entries
    should only change when a result does."""
    located: dict[tuple[str, int, str], list[str]] = collections.defaultdict(list)
    for result in results:
        for m in result.markers:
            if not m.passed:
                entry = type_entry(m.marker.path, m.failures[0].rule, m.marker.key)
                located[(m.marker.path, m.marker.line, entry)] += [d.message for d in m.failures]
        for d in result.unexpected:
            located[(d.path, d.line, type_entry(d.path, d.rule, result.line_key(d.path, d.line)))].append(d.message)
    entries: dict[str, list[str]] = {}
    for _, _, entry in sorted(located):
        entries.setdefault(entry, [])
    for (_, _, entry), messages in located.items():
        entries[entry] += [m for m in messages if m not in entries[entry]]
    return {entry: "; ".join(messages) for entry, messages in entries.items()}


# --- one recorded-results file --------------------------------------------------------------------------------------


@dataclass
class Changes:
    new: list[str] = field(default_factory=list)
    gone: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)  # same entry, different body (IDE sections)

    def __bool__(self) -> bool:
        return bool(self.new or self.gone or self.changed)


def owned(key: str, addons: list[Addon]) -> bool:
    path = entry_path(key)
    return any(a.contains(path) for a in addons)


def compare(recorded: dict[str, str], actual: dict[str, str], selected: list[Addon], existing: list[Addon]) -> Changes:
    """How ``actual`` (a run over ``selected``) differs from the recorded entries.

    The run is compared with the entries of the selected addons, and with those of no addon in ``existing``: a stale
    entry of a removed or renamed addon shows up as gone.
    """
    expected = {k: v for k, v in recorded.items() if owned(k, selected) or not owned(k, existing)}
    return Changes(
        new=[k for k in actual if k not in expected],
        gone=[k for k in expected if k not in actual],
        changed=[k for k in actual if k in expected and expected[k] != actual[k]],
    )


def merge(recorded: dict[str, str], actual: dict[str, str], selected: list[Addon], existing: list[Addon]) -> dict:
    """The recorded entries after ``--update``: the run's entries replace those ``compare`` looked at.

    Entries keep their order within a file; files are sorted by path.
    """
    kept = {k: v for k, v in recorded.items() if not owned(k, selected) and owned(k, existing)}
    merged = {**kept, **actual}
    return {k: merged[k] for k in sorted(merged, key=entry_path)}


def read_lines(path: Path) -> dict[str, str]:
    """A ``.txt`` file: one entry per line, ``#`` lines are comments."""
    if not path.is_file():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line: "" for line in lines if line and not line.startswith("#")}


def write_lines(path: Path, header: list[str], entries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {h}" for h in header] + list(entries)) + "\n", encoding="utf-8")


def read_sections(path: Path) -> dict[str, str]:
    """A ``.md`` file: one entry per ``## `` section, its title is the key and its text the body."""
    sections: dict[str, str] = {}
    if not path.is_file():
        return sections
    title = None
    body: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if title is not None:
                sections[title] = "\n".join(body).strip()
            title, body = line[3:], []
        elif title is not None:
            body.append(line)
    if title is not None:
        sections[title] = "\n".join(body).strip()
    return sections


def write_sections(path: Path, header: list[str], sections: dict[str, str]) -> None:
    out = list(header)
    for title, body in sections.items():
        out += ["", f"## {title}", "", body]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def progress_file(generator: str, version: str) -> Path:
    return EXPECTED_DIR / generator / f"{version}.progress.md"


# --- the two kinds of recorded results, and recording a run ---------------------------------------------------------


@dataclass(frozen=True)
class Kind:
    task: str  # the mise task that records it
    suffix: str
    keeps_bodies: bool  # whether an entry's body is recorded and compared, or only shown (ty's messages)
    read: Callable[[Path], dict[str, str]]
    write: Callable[[Path, list[str], dict[str, str]], None]
    header: Callable[[str, str], list[str]]

    def file(self, generator: str, version: str) -> Path:
        return EXPECTED_DIR / generator / f"{version}{self.suffix}"


FEATURES = Kind(
    "check:features",
    ".txt",
    False,
    read_lines,
    write_lines,
    lambda generator, version: [
        f"Feature-test results that are not passes, {generator} stubs, Blender {version}.",
        f"`mise run check:features {version}` fails when they change; `--update` rewrites this file.",
        "Format: path | rule | source line (with #2, #3 ... when the same text occurs again in the file)",
    ],
)
IDE = Kind(
    "check:ide",
    ".ide.md",
    True,
    read_sections,
    write_sections,
    lambda generator, version: [
        f"# IDE results, {generator} stubs, Blender {version}",
        "",
        f"Written by `mise run check:ide {version} --update`; the task fails when this file would change.",
        "Each section is one marker, `path | ^marker @column | queried line`, and what ty's language server returned.",
    ],
)


def describe(changes: Changes, recorded: dict[str, str], actual: dict[str, str], kind: Kind) -> list[str]:
    """The lines that show ``changes``: ``-`` gone, ``~`` changed, ``+`` new; under each, how its recorded body
    changed (IDE sections) or, for a new entry, ty's message. Then the counts per feature when several changed."""
    out = []

    def body_diff(before: str, after: str) -> list[str]:
        diff = difflib.unified_diff(before.splitlines(), after.splitlines(), "recorded", "now", lineterm="", n=1)
        return [f"        {line}" for line in list(diff)[2:]]

    for key in changes.gone:
        out.append(f"    - {key}")
        if kind.keeps_bodies:
            out += body_diff(recorded.get(key, ""), "")
    for key in changes.changed:
        out.append(f"    ~ {key}")
        out += body_diff(recorded.get(key, ""), actual.get(key, ""))
    for key in changes.new:
        out.append(f"    + {key}")
        if kind.keeps_bodies:
            out += body_diff("", actual.get(key, ""))
        elif actual.get(key):
            out.append(f"        {actual[key]}")

    per_feature: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for sign, keys in (("-", changes.gone), ("~", changes.changed), ("+", changes.new)):
        for key in keys:
            per_feature[feature_of(entry_path(key)) or "(other)"][sign] += 1
    if len(per_feature) > 1:
        counts = (
            f"{feature} " + " ".join(f"{sign}{n}" for sign, n in sorted(c.items()))
            for feature, c in per_feature.items()
        )
        out.append(f"    per feature: {', '.join(counts)}")
    return out


def record(
    kind: Kind, generator: str, version: str, actual: dict[str, str], selected: list[Addon], *, update: bool
) -> bool:
    """Compare a run over ``selected`` with the recorded results and print what changed, or with ``update`` merge
    it into them and rewrite the progress table. Returns whether the run differs from the record (a failure)."""
    path = kind.file(generator, version)
    shown = path.relative_to(REPO_ROOT).as_posix()
    stored = actual if kind.keeps_bodies else dict.fromkeys(actual, "")
    recorded = kind.read(path)
    existing = all_addons()
    if update:
        kind.write(path, kind.header(generator, version), merge(recorded, stored, selected, existing))
        log(f"Wrote {shown} and {write_progress(generator, version).relative_to(REPO_ROOT).as_posix()}")
        return False
    if not path.is_file():
        log(f"No recorded results in {shown}; run with --update to record them")
        return True
    changes = compare(recorded, stored, selected, existing)
    if not changes:
        log(f"Results match {shown}")
        return False
    log(
        f"Results changed against {shown} ({len(changes.gone)} gone, {len(changes.changed)} changed, "
        f"{len(changes.new)} new; `mise run {kind.task} {version} --update` records them):"
    )
    for line in describe(changes, recorded, actual, kind):
        print(line, flush=True)
    return True


# --- progress ---------------------------------------------------------------------------------------------------------


@dataclass
class FeatureProgress:
    feature: str
    asserts: list[int] = field(default_factory=lambda: [0, 0])  # passed, total
    expected_errors: list[int] = field(default_factory=lambda: [0, 0])
    guards: list[int] = field(default_factory=lambda: [0, 0])  # ``# bare-ok`` markers, of either kind
    ide: list[int] = field(default_factory=lambda: [0, 0])
    other: int = 0


def feature_of(path: str) -> str:
    """``features/<feature>/...`` -> ``<feature>``."""
    parts = path.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "features" else ""


def progress(
    features: list[str],
    type_markers: list[TypeMarker],
    ide: list[IdeMarker],
    recorded_types: dict[str, str],
    recorded_ide: dict[str, str] | None,
) -> list[FeatureProgress]:
    """Passes per feature. A type marker passes when no failure of it is recorded; an IDE marker that asserts
    something passes when its recorded section has no FAIL (``^hover`` and ``^signature`` only record, and are not
    counted). Guards (``# bare-ok``) hold without ty-blender, so they measure no progress: they get their own count
    instead of the assert_type or expected-error one. Recorded type entries that are no marker failure count as other
    diagnostics."""
    rows = {f: FeatureProgress(f) for f in features}
    consumed = set()
    for m in type_markers:
        row = rows[feature_of(m.path)]
        failures = {type_entry(m.path, r, m.key) for r in m.failure_rules} & recorded_types.keys()
        consumed |= failures
        counts = row.guards if m.bare_ok else row.asserts if m.kind == ASSERT else row.expected_errors
        counts[0] += not failures
        counts[1] += 1
    for key in recorded_types.keys() - consumed:
        if (feature := feature_of(entry_path(key))) in rows:
            rows[feature].other += 1
    for m in ide:
        if not m.asserts:
            continue
        row = rows[feature_of(m.path)]
        body = (recorded_ide or {}).get(m.title)
        row.ide[0] += body is not None and "FAIL" not in body
        row.ide[1] += 1
    return list(rows.values())


def progress_markdown(title: str, rows: list[FeatureProgress], with_ide: bool) -> str:
    def cell(counts: list[int]) -> str:
        return f"{counts[0]}/{counts[1]}" if counts[1] else "-"

    total = FeatureProgress("**total**")
    for r in rows:
        for name in ("asserts", "expected_errors", "guards", "ide"):
            getattr(total, name)[0] += getattr(r, name)[0]
            getattr(total, name)[1] += getattr(r, name)[1]
        total.other += r.other
    out = [
        f"# {title}",
        "",
        "Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of",
        "`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers",
        "that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.",
        "",
        "| Feature | assert_type | expected errors | guards | IDE | other diagnostics |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in [*rows, total]:
        ide = cell(r.ide) if with_ide else "not recorded"
        out.append(
            f"| {r.feature} | {cell(r.asserts)} | {cell(r.expected_errors)} | {cell(r.guards)} | {ide} | {r.other} |"
        )
    return "\n".join(out) + "\n"


def write_progress(generator: str, version: str) -> Path:
    """Rewrite ``<version>.progress.md`` for every feature from the recorded results and the current markers."""
    addons = all_addons()
    type_markers = [m for a in addons for f in type_files(a).values() for m in f.markers]
    ide = [m for a in addons for m in ide_markers(a)]
    ide_path = IDE.file(generator, version)
    recorded_ide = read_sections(ide_path) if ide_path.is_file() else None
    rows = progress(feature_names(), type_markers, ide, read_lines(FEATURES.file(generator, version)), recorded_ide)
    path = progress_file(generator, version)
    title = f"Feature-test progress, {generator} stubs, Blender {version}"
    path.write_text(progress_markdown(title, rows, recorded_ide is not None), encoding="utf-8")
    return path
