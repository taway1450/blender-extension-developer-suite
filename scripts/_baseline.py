"""The recorded results in ``tests/typecheck/expected/<generator>/<version>.*`` and the progress table built from them.

Three files per stub generator and Blender version:

- ``<version>.txt``: the ``check:features`` results that are not passes, one entry per line;
- ``<version>.ide.md``: every ``check:ide`` result, one section per marker;
- ``<version>.progress.md``: passes per feature, computed from the other two and the markers in the source.

An entry is named by its file and line key (``_markers.line_keys``), never by line number, so moving code does not
change it. Every entry starts with its path and `` | ``; that is how a partial run finds the entries it owns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from _common import TYPECHECK_TESTS_DIR
from _features import Addon, AddonResult, all_addons, feature_names, ide_markers, type_files
from _markers import ASSERT, IdeMarker, TypeMarker

EXPECTED_DIR = TYPECHECK_TESTS_DIR / "expected"
SEPARATOR = " | "


def entry_path(key: str) -> str:
    return key.partition(SEPARATOR)[0]


def type_entry(path: str, rule: str, line_key: str) -> str:
    """A ``check:features`` result: ``path | rule | line key``."""
    return f"{path}{SEPARATOR}{rule}{SEPARATOR}{line_key}"


def type_entries(results: list[AddonResult]) -> list[str]:
    """Everything that is not a pass, one entry per (line, rule), in file and line order. ty's messages are left
    out: they change with every type-rendering tweak, while the entries should only change when a result does."""
    located = set()
    for result in results:
        for m in result.markers:
            if not m.passed:
                located.add((m.marker.path, m.marker.line, type_entry(m.marker.path, m.failures[0].rule, m.marker.key)))
        for d in result.unexpected:
            located.add((d.path, d.line, type_entry(d.path, d.rule, result.line_key(d.path, d.line))))
    ordered = []
    for _, _, entry in sorted(located):
        if entry not in ordered:
            ordered.append(entry)
    return ordered


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


def features_file(generator: str, version: str) -> Path:
    return EXPECTED_DIR / generator / f"{version}.txt"


def ide_file(generator: str, version: str) -> Path:
    return EXPECTED_DIR / generator / f"{version}.ide.md"


def progress_file(generator: str, version: str) -> Path:
    return EXPECTED_DIR / generator / f"{version}.progress.md"


# --- progress ---------------------------------------------------------------------------------------------------------


@dataclass
class FeatureProgress:
    feature: str
    asserts: list[int] = field(default_factory=lambda: [0, 0])  # passed, total
    expected_errors: list[int] = field(default_factory=lambda: [0, 0])
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
    counted). Recorded type entries that are no marker failure count as other diagnostics."""
    rows = {f: FeatureProgress(f) for f in features}
    consumed = set()
    for m in type_markers:
        row = rows[feature_of(m.path)]
        failures = {type_entry(m.path, r, m.key) for r in m.failure_rules} & recorded_types.keys()
        consumed |= failures
        counts = row.asserts if m.kind == ASSERT else row.expected_errors
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
        for name in ("asserts", "expected_errors", "ide"):
            getattr(total, name)[0] += getattr(r, name)[0]
            getattr(total, name)[1] += getattr(r, name)[1]
        total.other += r.other
    out = [
        f"# {title}",
        "",
        "Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of",
        "`check:features` and `check:ide` from the recorded results next to this file; do not edit.",
        "",
        "| Feature | assert_type | expected errors | IDE | other diagnostics |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in [*rows, total]:
        ide = cell(r.ide) if with_ide else "not recorded"
        out.append(f"| {r.feature} | {cell(r.asserts)} | {cell(r.expected_errors)} | {ide} | {r.other} |")
    return "\n".join(out) + "\n"


def write_progress(generator: str, version: str) -> Path:
    """Rewrite ``<version>.progress.md`` for every feature from the recorded results and the current markers."""
    addons = all_addons()
    type_markers = [m for a in addons for f in type_files(a).values() for m in f.markers]
    ide = [m for a in addons for m in ide_markers(a)]
    ide_path = ide_file(generator, version)
    recorded_ide = read_sections(ide_path) if ide_path.is_file() else None
    rows = progress(feature_names(), type_markers, ide, read_lines(features_file(generator, version)), recorded_ide)
    path = progress_file(generator, version)
    title = f"Feature-test progress, {generator} stubs, Blender {version}"
    path.write_text(progress_markdown(title, rows, recorded_ide is not None), encoding="utf-8")
    return path
