"""The catalog of Blender-Python features in ``examples/catalog/``: its entries, the verdict on them, their pages.

An entry is a ``.py`` file (a script outside any add-on, or a single-file add-on) or a package directory (an add-on)
in a topic folder. Its main file (the ``.py`` file, or the package's ``__init__.py``) starts with a ``# /// catalog``
TOML header, then a module docstring (the prose, in Markdown) and checked code (see ``examples/catalog/README.md``)::

    # /// catalog
    # title = "Enum items that unpack another tuple"
    # section = "value-types"
    # status = "not-handled"
    # [future]
    # class = "planned"
    # note = "..."
    # tracked = "later/enum-items-unpacked"
    # ///
    \"\"\"Static `items` give the property a `Literal` Value type. ...\"\"\"

The code carries the feature tests' markers (``assert_type``, ``# ty: ignore[rule]``) and the Gap tag, a
``# gap: <reason>`` comment line saying the statement below it fails today. ``# catalog: hide`` and
``# catalog: show`` lines keep imports and wrapper functions off the page.

``check_addons.py --catalog`` type-checks the entries and records the results with a ``checked`` line per entry
(``checked_entries``). ``generate_catalog.py`` reads them back without running ty, judges each entry (``verdict``)
and writes ``docs/catalog/`` (``pages``).
"""

from __future__ import annotations

import ast
import functools
import hashlib
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from _baseline import CATALOG, EXAMPLES_EXPECTED_DIR, entry_path, type_entry
from _common import BLENDER_SUBMODULE, CATALOG_DIR, REPO_ROOT, entry_key
from _features import FEATURES_DIR, Addon
from _markers import ASSERT, EXPECTED, EXPECTED_ERROR, TypeMarker, parse_type_file
from examples_coverage import Demo, file_demos, read_results, table

HEADER_START = "# /// catalog"
HEADER_END = "# ///"
# The header's opening line may carry the marker of a result ty reports on a module's first line (a missing entry
# point, a problem in the manifest), since the header takes that line.
HEADER_START_LINE = re.compile(r"^# /// catalog(?P<marker>\s+#\s*ty:\s*ignore\[[^\]]+\])?\s*$")
MANIFEST = "blender_manifest.toml"  # shown on a package entry's page after its Python files
CHECKED = "checked"  # the rule column of an entry's ``checked`` line in the recorded results
HASH_LENGTH = 12
GAP = re.compile(r"^\s*#\s*gap:\s*(?P<id>.*?)\s*$")
HIDE = "# catalog: hide"
SHOW = "# catalog: show"

TOPICS_TOML = CATALOG_DIR / "topics.toml"
TY_TOML = CATALOG_DIR / "ty.toml"
PAGES_DIR = REPO_ROOT / "docs" / "catalog"
COVERAGE_TOML = REPO_ROOT / "examples" / "addons" / "coverage.toml"
REMAINING_CAUSES = REPO_ROOT / "docs" / "reports" / "remaining-causes.md"
BLENDER_DOCS_RST = "doc/python_api/rst"  # in the Blender source
# The results every verdict is read from (as for examples:coverage): the builtin stubs know the most, main is newest.
REFERENCE = ("builtin", "main")
# The other recorded results an entry is compared with (``[differs]``).
OTHERS = (("fake-bpy-module", "main"), ("builtin", "5.2"), ("fake-bpy-module", "5.2"))
RULES_URL = "https://github.com/taway1450/ruff-blender/blob/blender/crates/ty/docs/rules.md"
BLENDER_DOCS_URL = "https://docs.blender.org/api/current"
ANY_RULE_HEADING = re.compile(r"^## `(?P<rule>[a-z][a-z0-9-]*)`$")


def is_other(key: str) -> bool:
    """Whether ``key`` (``generator/version``) names one of the other recorded results."""
    return tuple(key.split("/", 1)) in OTHERS


STATUSES = {"handled": "Handled", "partial": "Partial", "not-handled": "Not handled", "unknown": "Unknown"}
# Safeguards, in page order. The first six find a problem before the add-on runs (a checked marker shows it); the
# linter profile and Blender itself do not type-check, so their entries need no marker.
SAFEGUARDS = (
    "stub-generator",
    "runtime-probe",
    "source-parser",
    "typechecker",
    "runtime-typechecker",
    "blender-fix",
    "linter-profile",
    "blender-runtime",
)
STATIC_SAFEGUARDS = SAFEGUARDS[:6]
CLASSES = {
    "planned": "Planned",
    "possible": "Possible",
    "not-checkable": "Not statically checkable",
    "out-of-scope": "Out of scope",
}
NEEDS_GAP = ("planned", "possible")  # a class whose entry shows what fails today
HEADER_KEYS = {
    "title",
    "section",
    "status",
    "safeguards",
    "features",
    "later",
    "note",
    "evidence",
    "blender-docs",
    "see",
    "future",
    "differs",
    "runtime",
}
FUTURE_KEYS = {"class", "note", "tracked"}  # all strings
RUNTIME_KEYS = {"register", "error", "reason", "probe"}
# `[evidence]`: a feature-test add-on, and what its _expected/runtime.toml must say for the entry's claim to hold.
EVIDENCE_KEYS = {"addon", "register", "says"}  # all strings
PROBE_KEYS = {"code", "expect", "reason"}
DOCS_PAGE = re.compile(r"^(info_[a-z_]+|[a-z][a-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*)$")
# Modules of Blender's Python an entry may import, which an entry's file stem would shadow.
BLENDER_MODULES = {
    "bpy",
    "bpy_extras",
    "bmesh",
    "mathutils",
    "gpu",
    "gpu_extras",
    "aud",
    "bl_math",
    "blf",
    "idprop",
    "imbuf",
    "freestyle",
    "bl_ui",
    "bl_operators",
    "addon_utils",
    "rna_prop_ui",
}
# Abbreviations whose full stop ends no sentence.
ABBREVIATION = re.compile(r"(?:^|[\s(])(?:e\.g|i\.e|etc|vs|cf|approx)\.$", re.IGNORECASE)
GENERATED_NOTE = (
    "<!-- Generated by `mise run catalog:generate` from examples/catalog/: edit the entries, not this file. -->"
)


# --- the recorded results --------------------------------------------------------------------------------------------


def split_header(text: str) -> tuple[list[str], list[str]]:
    """The lines of the ``# /// catalog`` block (without its fences) and every other line, in order. No block gives
    an empty header."""
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if HEADER_START_LINE.match(line):
            for end in range(start + 1, len(lines)):
                if lines[end].rstrip() == HEADER_END:
                    return lines[start + 1 : end], lines[:start] + lines[end + 1 :]
            break
    return [], lines


def opening_marker(text: str) -> str:
    """The ``# ty: ignore[...]`` the header's opening line carries, or ``""``."""
    first = text.splitlines()[:1]
    match = HEADER_START_LINE.match(first[0]) if first else None
    return match["marker"].strip() if match and match["marker"] else ""


def entry_files(entry: Addon) -> list[Path]:
    """Every file ty may read for the entry: the ``.py`` file, or all files of the package (its
    ``blender_manifest.toml`` too)."""
    if entry.path.is_file():
        return [entry.path]
    return sorted(p for p in entry.path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def code_hash(entry: Addon) -> str:
    """A short hash of the entry's code: every file of it, the Python files without their header, so editing only
    the header (its status, its notes) does not ask for another ``check:catalog`` run. A marker on the header's
    opening line counts, since ty reads it. Line endings do not count."""
    digest = hashlib.sha256()
    for path in entry_files(entry):
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            marker = opening_marker(text)
            code = ([marker] if marker else []) + split_header(text)[1]
        else:
            code = text.splitlines()
        digest.update(path.relative_to(entry.path.parent).as_posix().encode())
        digest.update(b"\0" + "\n".join(code).encode() + b"\0")
    return digest.hexdigest()[:HASH_LENGTH]


def checked_line(entry: Addon) -> str:
    """The recorded line that says the entry was checked as its code is now: ``path | checked | hash``."""
    return type_entry(entry.rel, CHECKED, code_hash(entry))


def owner(key: str, entries: list[Addon]) -> str:
    """The path of the entry a recorded line belongs to (its own path when none does)."""
    path = entry_path(key)
    return next((entry.rel for entry in entries if entry.contains(path)), path)


def checked_entries(entries: list[Addon], results: dict[str, str]) -> dict[str, str]:
    """A run's results with each entry's ``checked`` line before its own results."""
    merged = {**{checked_line(entry): "" for entry in entries}, **results}
    order = {key: index for index, key in enumerate(merged)}
    return {key: merged[key] for key in sorted(merged, key=lambda key: (owner(key, entries), order[key]))}


@dataclass
class Recorded:
    """One recorded-results file: the hash each entry was checked with, and its results as (path, rule, key)."""

    hashes: dict[str, str] = field(default_factory=dict)  # entry path -> hash
    results: set[tuple[str, str, str]] = field(default_factory=set)

    def of(self, rel: str) -> set[tuple[str, str, str]]:
        """The results of the entry at ``rel`` (a file, or a package directory)."""
        return {r for r in self.results if r[0] == rel or r[0].startswith(f"{rel}/")}


def read_recorded(path: Path) -> Recorded:
    recorded = Recorded()
    for file, rule, key in read_results(path, CATALOG):
        if rule == CHECKED:
            recorded.hashes[file] = key
        else:
            recorded.results.add((file, rule, key))
    return recorded


def recorded_file(generator: str, version: str) -> Path:
    return CATALOG.file(generator, version, EXAMPLES_EXPECTED_DIR)


# --- topics.toml ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    to_come: tuple[str, ...] = ()


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    covers: str
    intro: str
    sections: tuple[Section, ...]


@dataclass
class Topics:
    """``examples/catalog/topics.toml``: the catalog's intro, its topics in order, what each safeguard and class is,
    and blanket notes for results that differ with another stub generator or Blender version."""

    intro: str = ""
    topics: list[Topic] = field(default_factory=list)
    safeguards: dict[str, dict[str, str]] = field(default_factory=dict)  # id -> title, description
    classes: dict[str, str] = field(default_factory=dict)  # id -> description
    differs: dict[str, str] = field(default_factory=dict)  # "generator/version" -> note
    problems: list[str] = field(default_factory=list)

    def topic(self, topic_id: str) -> Topic | None:
        return next((t for t in self.topics if t.id == topic_id), None)


def read_topics(text: str) -> Topics:
    data = tomllib.loads(text)
    result = Topics(
        intro=data.get("intro", ""),
        safeguards=data.get("safeguard", {}),
        classes=data.get("class", {}),
        differs=data.get("differs", {}),
    )
    for unknown in sorted(set(data) - {"intro", "topic", "safeguard", "class", "differs"}):
        result.problems.append(f"topics.toml: unknown key `{unknown}`")
    for topic_id, topic in data.get("topic", {}).items():
        sections = []
        for section in topic.get("sections", []):
            if not section.get("id") or not section.get("title"):
                result.problems.append(f"topics.toml: a section of `{topic_id}` has no id or title")
                continue
            sections.append(Section(section["id"], section["title"], tuple(section.get("to-come", []))))
        for key in ("title", "covers", "intro"):
            if not topic.get(key):
                result.problems.append(f"topics.toml: topic `{topic_id}` has no {key}")
        ids = [s.id for s in sections]
        if len(set(ids)) != len(ids):
            result.problems.append(f"topics.toml: topic `{topic_id}` has two sections of the same id")
        result.topics.append(
            Topic(
                topic_id, topic.get("title", topic_id), topic.get("covers", ""), topic.get("intro", ""), tuple(sections)
            )
        )
    for kind, known, given in (("safeguard", SAFEGUARDS, result.safeguards), ("class", CLASSES, result.classes)):
        result.problems += [f"topics.toml: no [{kind}.{name}]" for name in known if name not in given]
        result.problems += [f"topics.toml: [{kind}.{name}] is no {kind}" for name in given if name not in known]
    for name, safeguard in result.safeguards.items():
        if not safeguard.get("title") or not safeguard.get("description"):
            result.problems.append(f"topics.toml: [safeguard.{name}] needs a title and a description")
    for key in result.differs:
        if not is_other(key):
            result.problems.append(f"topics.toml: [differs] `{key}` is no other recorded generator/version")
    return result


# --- an entry ---------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Header:
    title: str = ""
    section: str = ""
    status: str = "unknown"
    safeguards: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    later: str = ""
    note: str = ""
    evidence: dict = field(default_factory=dict)
    blender_docs: tuple[str, ...] = ()
    see: tuple[str, ...] = ()
    future: dict = field(default_factory=dict)
    differs: dict[str, str] = field(default_factory=dict)
    runtime: dict = field(default_factory=dict)


def parse_header(where: str, lines: list[str]) -> tuple[Header, list[str]]:
    """The header from its comment lines, and what is wrong with it (unknown keys, a wrong type or value, a key that
    the status needs and that is missing)."""
    problems: list[str] = []
    body = []
    for line in lines:
        if line.rstrip() == "#":
            body.append("")
        elif line.startswith("# "):
            body.append(line[2:])
        else:
            problems.append(f"{where}: a header line that is not a `# ` comment: {line!r}")
    try:
        data = tomllib.loads("\n".join(body))
    except tomllib.TOMLDecodeError as error:
        return Header(), [*problems, f"{where}: the header is no valid TOML: {error}"]
    problems += [f"{where}: unknown header key `{key}`" for key in sorted(set(data) - HEADER_KEYS)]

    def text(key: str) -> str:
        value = data.get(key, "")
        if not isinstance(value, str):
            problems.append(f"{where}: `{key}` must be a string")
            return ""
        return value

    def texts(key: str) -> tuple[str, ...]:
        value = data.get(key, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            problems.append(f"{where}: `{key}` must be a list of strings")
            return ()
        return tuple(value)

    def mapping(key: str, keys: set[str] | None, strings: bool = False) -> dict:
        """The table ``key``; with ``strings``, a value that is no string is reported and left out."""
        value = data.get(key, {})
        if not isinstance(value, dict):
            problems.append(f"{where}: `{key}` must be a table")
            return {}
        if keys is not None:
            problems.extend(f"{where}: unknown key `{key}.{k}`" for k in sorted(set(value) - keys))
        if strings:
            wrong = sorted(k for k, v in value.items() if not isinstance(v, str))
            problems.extend(f"{where}: `{key}.{k}` must be a string" for k in wrong)
            value = {k: v for k, v in value.items() if k not in wrong}
        return value

    header = Header(
        title=text("title"),
        section=text("section"),
        status=text("status") or "unknown",
        safeguards=texts("safeguards"),
        features=texts("features"),
        later=text("later"),
        note=text("note"),
        evidence=mapping("evidence", EVIDENCE_KEYS, strings=True),
        blender_docs=texts("blender-docs"),
        see=texts("see"),
        future=mapping("future", FUTURE_KEYS, strings=True),
        differs=mapping("differs", None),
        runtime=mapping("runtime", RUNTIME_KEYS),
    )
    for key in ("title", "section", "status"):
        if key not in data:
            problems.append(f"{where}: the header needs `{key}`")
    if header.status and header.status not in STATUSES:
        problems.append(f"{where}: status `{header.status}` is none of {', '.join(STATUSES)}")
    problems += [
        f"{where}: `{h}` is no safeguard ({', '.join(SAFEGUARDS)})" for h in header.safeguards if h not in SAFEGUARDS
    ]
    if header.status in ("handled", "partial") and not header.safeguards:
        problems.append(f"{where}: a {header.status} entry names its `safeguards`")
    if header.status in ("not-handled", "unknown") and header.safeguards:
        problems.append(f"{where}: a {header.status} entry has no `safeguards`")
    if header.status == "partial" and not header.note:
        problems.append(f"{where}: a partial entry says in `note` what is missing")
    if header.status == "not-handled" and not header.future:
        problems.append(f"{where}: a not-handled entry needs a [future] table")
    if header.future:
        cls = header.future.get("class", "")
        if cls not in CLASSES:
            problems.append(f"{where}: [future] class `{cls}` is none of {', '.join(CLASSES)}")
        if not header.future.get("note"):
            problems.append(f"{where}: [future] needs a `note` (what would handle it, or why nothing can)")
        if cls == "planned" and not header.future.get("tracked"):
            problems.append(f"{where}: a planned entry says where it is `tracked`")
        if header.status not in ("not-handled", "partial"):
            problems.append(f"{where}: only a not-handled or partial entry has a [future] table")
    for key, note in header.differs.items():
        if not is_other(key):
            problems.append(f"{where}: [differs] `{key}` is no other recorded generator/version")
        if not isinstance(note, str) or not note:
            problems.append(f"{where}: [differs] `{key}` needs the reason as a string")
    if header.evidence:
        if not header.evidence.get("addon"):
            problems.append(f"{where}: [evidence] names the feature-test `addon`")
        if header.evidence.get("register", "ok") not in ("ok", "fails"):
            problems.append(f"{where}: [evidence] register is `ok` or `fails`")
    if "blender-runtime" in header.safeguards and not (header.evidence or header.runtime):
        problems.append(f"{where}: `blender-runtime` needs `evidence` or a [runtime] table")
    if header.runtime:
        if header.runtime.get("register", "ok") not in ("ok", "fails"):
            problems.append(f"{where}: [runtime] register is `ok` or `fails`")
        for probe in header.runtime.get("probe", []):
            if not isinstance(probe, dict) or "code" not in probe or "expect" not in probe:
                problems.append(f"{where}: each [[runtime.probe]] has `code` and `expect`")
            else:
                problems.extend(f"{where}: unknown key `runtime.probe.{k}`" for k in sorted(set(probe) - PROBE_KEYS))
    return header, problems


@dataclass
class Entry:
    topic: str
    stem: str
    rel: str  # the file or package directory, relative to examples/catalog
    main: str  # the file with the header and the prose, relative to examples/catalog
    header: Header
    prose: str
    texts: dict[str, str]  # every Python file of the entry by path relative to examples/catalog, main first
    problems: list[str] = field(default_factory=list)

    @property
    def anchor(self) -> str:
        return entry_key(self.stem)

    @property
    def id(self) -> str:
        return f"{self.topic}/{self.anchor}"

    @property
    def is_addon(self) -> bool:
        """Whether Blender would take the entry for an add-on: a package, or a module with ``bl_info``."""
        return self.main.endswith("/__init__.py") or assigns_bl_info(self.texts[self.main])

    def gaps(self) -> list[Demo]:
        """The Gap tags of every file of the entry, each with the statement below it."""
        found: list[Demo] = []
        for path, text in self.texts.items():
            found += file_demos(path, text, GAP)
        return found

    def markers(self) -> list[TypeMarker]:
        return [m for path, text in self.texts.items() for m in parse_type_file(path, text).markers]

    def holding_markers(self) -> list[TypeMarker]:
        """The markers outside every Gap-tagged statement."""
        gapped = {(g.path, key) for g in self.gaps() for key in g.keys}
        return [m for m in self.markers() if (m.path, m.key) not in gapped]

    @property
    def checked(self) -> bool:
        """Whether the entry makes a machine-checked claim: a marker, or a Gap tag."""
        return bool(self.markers() or self.gaps())


def assigns_bl_info(text: str) -> bool:
    """Whether the module assigns ``bl_info`` at its top level."""
    try:
        body = ast.parse(text).body
    except SyntaxError:
        return False
    for node in body:
        targets = (
            node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if any(isinstance(t, ast.Name) and t.id == "bl_info" for t in targets):
            return True
    return False


def load_entry(addon: Addon) -> Entry:
    """The entry of a catalog addon (``_features.catalog_entry_list``), with the problems of its files."""
    main_path = addon.path if addon.path.is_file() else addon.path / "__init__.py"
    texts = {}
    for path in [main_path, *(p for p in addon.python_files() if p != main_path)]:
        texts[path.relative_to(CATALOG_DIR).as_posix()] = path.read_text(encoding="utf-8")
    return make_entry(addon.feature, addon.path.stem, addon.rel, texts)


def make_entry(topic: str, stem: str, rel: str, texts: dict[str, str]) -> Entry:
    """The entry from the texts of its files (by path relative to examples/catalog, the main file first)."""
    main = next(iter(texts))
    header_lines, _ = split_header(texts[main])
    header, problems = parse_header(main, header_lines)
    if not header_lines:
        problems.append(f"{main}: no `{HEADER_START}` header")
    for path, text in texts.items():
        if path != main and split_header(text)[0]:
            problems.append(f"{path}: only the entry's main file has a header")
    try:
        prose = ast.get_docstring(ast.parse(texts[main]), clean=True) or ""
    except SyntaxError as error:
        prose, problems = "", [*problems, f"{main}: {error}"]
    if not prose:
        problems.append(f"{main}: the entry needs a module docstring (its prose)")
    for path, text in texts.items():
        problems += [
            f"{path}: a Gap tag needs a reason (`# gap: <reason>`)" for g in file_demos(path, text, GAP) if not g.id
        ]
    return Entry(topic, stem, rel, main, header, prose, texts, problems)


def first_sentence(prose: str) -> str:
    """The prose's first sentence, on one line: the entry's line in the indexes."""
    flat = " ".join(prose.split())
    for match in re.finditer(r"[.!?](?=\s|$)", flat):
        sentence = flat[: match.end()]
        if not ABBREVIATION.search(sentence):
            return sentence
    return flat


# --- what the code shows ----------------------------------------------------------------------------------------------


def display_line(line: str) -> str:
    """A line as the page shows it: an expected error reads as what is reported, a Gap tag as what is missing."""
    if gap := GAP.match(line):
        return f"{line[: len(line) - len(line.lstrip())]}# not handled yet: {gap['id']}"
    return EXPECTED_ERROR.sub(lambda m: f"# reported: {', '.join(r.strip() for r in m['rules'].split(','))}", line)


def shown_code(text: str) -> str:
    """The code of a file as its page shows it: without the header, the module docstring and the hidden parts.

    ``# catalog: hide`` hides the lines after it, ``# catalog: show`` shows them again. A shown part that is indented
    deeper than the hide line before it (the body of a hidden wrapper function) is dedented by the difference."""
    _, lines = split_header(text)
    tree = ast.parse("\n".join(lines))
    skip: set[int] = set()
    first = tree.body[0] if tree.body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        skip = set(range(first.lineno - 1, first.end_lineno or first.lineno))
    shown: list[str] = []
    hidden, hide_indent, dedent = False, 0, 0
    for index, line in enumerate(lines):
        if index in skip:
            continue
        stripped, indent = line.strip(), len(line) - len(line.lstrip())
        if stripped == HIDE:
            hidden, hide_indent = True, indent
        elif stripped == SHOW:
            hidden, dedent = False, max(0, indent - hide_indent)
        elif not hidden:
            shown.append(display_line(line[dedent:] if not line[:dedent].strip() else line).rstrip())
    return re.sub(r"\n{4,}", "\n\n\n", "\n".join(shown)).strip("\n")


def asserted(marker: TypeMarker, text: str) -> tuple[str, str] | None:
    """The expression and type of the ``assert_type`` call that starts on the marker's line of ``text`` (its file),
    as written, on one line each; the call may go on over more lines."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.lineno == marker.line and len(node.args) == 2):
            continue
        func = node.func
        if (func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")) != "assert_type":
            continue
        expression, type_ = (ast.get_source_segment(text, arg) for arg in node.args)
        if expression and type_:
            return " ".join(expression.split()), " ".join(type_.split())
    return None


# --- the verdict ------------------------------------------------------------------------------------------------------


def in_gap(result: tuple[str, str, str], gaps: list[Demo]) -> bool:
    path, _, key = result
    return any(g.path == path and key in g.keys for g in gaps)


def verdict(entry: Entry, reference: Recorded, current_hash: str) -> list[str]:
    """What is wrong with what the entry claims, judged against the reference results (``catalog:generate --check``
    fails on any of it):

    1. every recorded result lies in a Gap-tagged statement;
    2. every Gap-tagged statement still fails (has a recorded result);
    3. the status agrees with the markers and gaps;
    4. the entry was recorded as its code is now.
    """
    where, problems = entry.main, []
    recorded_hash = reference.hashes.get(entry.rel)
    if recorded_hash is None:
        return [f"{where}: never checked: run `mise run check:catalog main {entry.id} --update`"]
    if recorded_hash != current_hash:
        return [f"{where}: changed since it was checked: run `mise run check:catalog main {entry.id} --update`"]
    gaps, results = entry.gaps(), reference.of(entry.rel)
    for path, rule, key in sorted(results):
        if not in_gap((path, rule, key), gaps):
            problems.append(f"{path}: `{rule}` on `{key}`, which no Gap tag marks: fix the entry or tag it")
    for gap in gaps:
        if not any(in_gap(r, [gap]) for r in results):
            problems.append(f"{gap.where}: the gap holds now: remove the tag and review `status`")
    status, holding = entry.header.status, entry.holding_markers()
    static = any(h in STATIC_SAFEGUARDS for h in entry.header.safeguards)
    cls = entry.header.future.get("class", "")
    if status == "handled" and gaps:
        problems.append(f"{where}: a handled entry has no Gap tag")
    if status == "handled" and static and not holding:
        problems.append(f"{where}: a handled entry shows what the safeguard does with a marker")
    if status == "partial" and not (holding and gaps):
        problems.append(f"{where}: a partial entry has a marker that holds and a Gap tag")
    if status == "not-handled" and cls in NEEDS_GAP and not gaps:
        problems.append(f"{where}: a {cls} entry shows with a Gap tag what fails today")
    return problems


def differences(entry: Entry, reference: Recorded, others: dict[tuple[str, str], Recorded]) -> dict[str, bool]:
    """For each other recorded generator/version that checked the entry as it is now: whether its outcome differs."""
    mine = reference.of(entry.rel)
    found = {}
    for (generator, version), recorded in others.items():
        if recorded.hashes.get(entry.rel) == reference.hashes.get(entry.rel) and entry.rel in recorded.hashes:
            found[f"{generator}/{version}"] = recorded.of(entry.rel) != mine
    return found


def stale_recordings(entry: Entry, reference: Recorded, others: dict[tuple[str, str], Recorded]) -> list[str]:
    """The other recorded generators/versions that never checked the entry, or checked an older version of it: their
    outcome cannot be compared, so its ``[differs]`` notes cannot be judged until it is recorded there."""
    current = reference.hashes.get(entry.rel)
    if current is None:
        return []  # the verdict asks for the reference run first
    problems = []
    for (generator, version), recorded in others.items():
        if recorded.hashes.get(entry.rel) == current:
            continue
        what = "never checked" if entry.rel not in recorded.hashes else "recorded from older code"
        problems.append(
            f"{entry.main}: {what} with {generator} stubs, Blender {version}: run "
            f"`mise run check:catalog {version} {entry.id} --generator {generator} --update`"
        )
    return problems


def leftover_lines(entries: list[Entry], recorded: dict[str, Recorded]) -> list[str]:
    """Recorded lines of no current entry (one deleted or renamed), per recorded file."""
    problems = []
    for name, record in recorded.items():
        paths = set(record.hashes) | {path for path, _, _ in record.results}
        stale = sorted(p for p in paths if not any(p == e.rel or p.startswith(f"{e.rel}/") for e in entries))
        problems += [f"{name}: `{p}` is no entry any more: re-record with `--update`" for p in stale]
    return problems


def differs_problems(entry: Entry, found: dict[str, bool], blanket: dict[str, str]) -> list[str]:
    """A note is required where another recorded result differs (``[differs]`` or a blanket note in topics.toml),
    and the entry's own note must not stay once it does not."""
    problems = []
    for key, differs in found.items():
        if differs and key not in entry.header.differs and key not in blanket:
            problems.append(f"{entry.main}: the outcome differs with {key}: say why in [differs]")
        if not differs and key in entry.header.differs:
            problems.append(f"{entry.main}: [differs] `{key}` is stale: the outcome is the same")
    return problems


def evidence_problems(where: str, evidence: dict) -> list[str]:
    """Whether the feature-test add-on's ``_expected/runtime.toml`` says what ``[evidence]`` claims: the same
    ``register`` outcome, and ``says`` in its ``reason`` or ``error``."""
    path = FEATURES_DIR / evidence["addon"] / "_expected" / "runtime.toml"
    if not path.is_file():
        return [f"{where}: evidence `{evidence['addon']}` is no feature-test add-on with _expected/runtime.toml"]
    spec = tomllib.loads(path.read_text(encoding="utf-8"))
    problems = []
    claimed, recorded = evidence.get("register", "ok"), spec.get("register", "ok")
    if claimed != recorded:
        problems.append(f"{where}: [evidence] says register `{claimed}`, but {evidence['addon']} says `{recorded}`")
    says = evidence.get("says", "")
    if says and not any(says in spec.get(key, "") for key in ("reason", "error")):
        problems.append(f"{where}: [evidence] `{says}` is not in the reason or error of {evidence['addon']}")
    return problems


def header_problems(entry: Entry, topics: Topics, features: list[str], later: set[str]) -> list[str]:
    """What the header names that does not exist: its section, features, `later` topic, tracker, evidence, docs."""
    where, header, problems = entry.main, entry.header, []
    topic = topics.topic(entry.topic)
    if topic is None:
        problems.append(f"{where}: the topic folder `{entry.topic}` has no [topic.{entry.topic}] in topics.toml")
    elif header.section and header.section not in [s.id for s in topic.sections]:
        problems.append(f"{where}: `{header.section}` is no section of the topic `{entry.topic}`")
    problems += [f"{where}: `{name}` is no feature-test directory" for name in header.features if name not in features]
    if header.later:
        if header.later not in later:
            problems.append(f'{where}: `later = "{header.later}"` has no [later.{header.later}] in coverage.toml')
        if header.status not in ("partial", "not-handled"):
            problems.append(f"{where}: an entry with a `later` topic is partial or not handled")
    tracked = header.future.get("tracked", "")
    if tracked.startswith("later/") and tracked.removeprefix("later/") not in later:
        problems.append(
            f"{where}: tracked `{tracked}` has no [later.{tracked.removeprefix('later/')}] in coverage.toml"
        )
    elif tracked.startswith("remaining-causes/") and REMAINING_CAUSES.is_file():
        cause = tracked.removeprefix("remaining-causes/")
        if not re.search(rf"\b{re.escape(cause)}\b", REMAINING_CAUSES.read_text(encoding="utf-8")):
            problems.append(f"{where}: tracked `{tracked}` is not in docs/reports/remaining-causes.md")
    elif tracked and not re.fullmatch(r"later/.+|remaining-causes/.+|#\d+", tracked):
        problems.append(f"{where}: tracked `{tracked}` is none of later/<topic>, remaining-causes/<id>, #<issue>")
    if header.evidence.get("addon"):
        problems += evidence_problems(where, header.evidence)
    if header.runtime and not entry.is_addon:
        problems.append(f"{where}: an entry with a [runtime] table is an add-on (a package, or a module with bl_info)")
    for page in header.blender_docs:
        if not DOCS_PAGE.match(page):
            problems.append(f"{where}: blender-docs `{page}` is no page name (info_gotcha, bpy.props, ...)")
        elif page.startswith("info_") and in_blender_source(f"{BLENDER_DOCS_RST}/{page}.rst") is False:
            problems.append(f"{where}: blender-docs `{page}` is not in blender/{BLENDER_DOCS_RST}/")
    for path in header.see:
        if not path.startswith("blender/"):
            problems.append(f"{where}: see `{path}` is a path in the Blender source, starting with blender/")
        elif in_blender_source(path.removeprefix("blender/")) is False:
            problems.append(f"{where}: see `{path}` does not exist")
    return problems


@functools.cache
def blender_commit() -> str | None:
    """The Blender commit this repository pins, when the ``blender`` submodule has it: its tree is enough, so CI
    fetches it without file contents (``.github/workflows/scripts.yml``)."""
    pinned = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD:blender"], capture_output=True, text=True)
    commit = pinned.stdout.strip()
    if pinned.returncode or not (BLENDER_SUBMODULE / ".git").exists():
        return None
    known = subprocess.run(
        ["git", "-C", str(BLENDER_SUBMODULE), "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True
    )
    return commit if known.returncode == 0 else None


def in_blender_source(path: str) -> bool | None:
    """Whether ``path`` (relative to the Blender source) exists at the pinned commit; None when that cannot be told."""
    commit = blender_commit()
    if commit is None:
        return None
    listed = subprocess.run(
        ["git", "-C", str(BLENDER_SUBMODULE), "ls-tree", "--name-only", commit, "--", path.rstrip("/")],
        capture_output=True,
        text=True,
    )
    if listed.returncode:
        return None  # a tree git cannot read (an incomplete clone): not the same as a missing path
    return bool(listed.stdout.strip())


# --- the pages --------------------------------------------------------------------------------------------------------


def rule_link(rule: str, levels: dict[str, str]) -> str:
    level = f" ({levels[rule]})" if levels.get(rule) else ""
    return f"[`{rule}`]({RULES_URL}#{rule}){level}"


def joined(items: list[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def safeguard_links(entry: Entry, topics: Topics) -> str:
    return joined(
        [f"[{topics.safeguards.get(h, {}).get('title', h)}](by-safeguard.md#{h})" for h in entry.header.safeguards]
    )


def status_line(entry: Entry, topics: Topics) -> str:
    header = entry.header
    label = f"**{STATUSES.get(header.status, header.status)}**"
    if header.status == "handled":
        label += f" by {safeguard_links(entry, topics)}"
    elif header.status == "partial":
        label += f": handled in part by {safeguard_links(entry, topics)}"
    elif header.status == "not-handled":
        label += f" ({CLASSES.get(header.future.get('class', ''), '').lower()})"
    else:
        label += ": not classified yet"
    checked = "checked with Blender main, builtin stubs" if entry.checked else "not machine-checked"
    return f"{label} · {checked} · `{entry.id}`"


def what_you_see(entry: Entry, levels: dict[str, str]) -> str:
    """What the holding markers show: the types, then the rules reported on the marked lines."""
    parts = []
    holding = entry.holding_markers()
    expected = [m for m in holding if m.kind == EXPECTED]
    opening = [m for m in expected if m.line == 1 and opening_marker(entry.texts[m.path])]
    marked = [m for m in expected if m not in opening]
    for marker in holding:
        if marker.kind == ASSERT and (pair := asserted(marker, entry.texts[marker.path])):
            parts.append(f"`{pair[0]}` is `{pair[1]}`")
    for marker in opening:
        rules = joined([rule_link(r, levels) for r in marker.rules])
        parts.append(f"ty reports {rules} on the first line of `{marker.path.rsplit('/', 1)[-1]}`")
    rules = list(dict.fromkeys(r for m in marked for r in m.rules))
    if rules:
        lines = "the line" if len(marked) == 1 else "the lines"
        parts.append(f"ty reports {joined([rule_link(r, levels) for r in rules])} on {lines} marked *reported*")
    return "; ".join(parts)


def today(entry: Entry, reference: Recorded, levels: dict[str, str]) -> str:
    gaps = entry.gaps()
    rules = sorted({result[1] for result in reference.of(entry.rel) if in_gap(result, gaps)})
    if not rules:
        return ""
    where = "line" if len(gaps) == 1 else "lines"
    return f"ty reports {joined([rule_link(r, levels) for r in rules])} on the {where} marked *not handled yet*"


def future_line(entry: Entry) -> str:
    future = entry.header.future
    if not future:
        return ""
    text = f"{CLASSES.get(future.get('class', ''), '')}: {future.get('note', '')}"
    if future.get("tracked"):
        text += f" (tracked: `{future['tracked']}`)"
    return text


def in_blender(entry: Entry) -> str:
    """What the ``[runtime]`` table says ``check:load`` saw: whether the add-on registers, and each probe's reason."""
    runtime = entry.header.runtime
    if not runtime:
        return ""
    fails = runtime.get("register") == "fails"
    text = "the add-on fails to register" if fails else "the add-on registers"
    if reason := runtime.get("reason"):
        text += f" ({reason})"
    reasons = [p["reason"] for p in runtime.get("probe", []) if p.get("reason")]
    return "; ".join([text, *reasons]) + "."


def more_links(entry: Entry) -> str:
    links = [
        f"[feature tests: {name}](../../tests/typecheck/features/{name}/README.md)" for name in entry.header.features
    ]
    if addon := entry.header.evidence.get("addon"):
        links.append(f"[runtime evidence](../../tests/typecheck/features/{addon}/_expected/runtime.toml)")
    links += [f"[{page}]({BLENDER_DOCS_URL}/{page}.html)" for page in entry.header.blender_docs]
    links += [
        f"[`{path.removeprefix('blender/')}`](https://projects.blender.org/blender/blender/src/branch/main/{path.removeprefix('blender/')})"
        for path in entry.header.see
    ]
    links.append(f"[source](../../examples/catalog/{entry.rel})")
    return " · ".join(links)


def render_entry(entry: Entry, catalog: Catalog) -> list[str]:
    topics, levels, differ = catalog.topics, catalog.levels, catalog.differ.get(entry.id, {})
    out = [
        f'<a id="{entry.anchor}"></a>',
        f"### {entry.header.title}",
        "",
        status_line(entry, topics),
        "",
        entry.prose,
        "",
    ]
    for path, text in entry.texts.items():
        code = shown_code(text)
        if not code:
            continue
        if len(entry.texts) > 1:
            out += [f"`{path.removeprefix(entry.topic + '/')}`", ""]
        out += ["```python", code, "```", ""]
    if (manifest := CATALOG_DIR / entry.rel / MANIFEST).is_file():
        out += [f"`{entry.stem}/{MANIFEST}`", "", "```toml", manifest.read_text(encoding="utf-8").strip(), "```", ""]
    bullets = []
    if entry.header.status in ("handled", "partial") and (seen := what_you_see(entry, levels)):
        bullets.append(f"**What you see:** {seen}.")
    if entry.header.status == "partial":
        bullets.append(f"**Not yet:** {entry.header.note}")
    elif entry.header.note:
        bullets.append(f"**Note:** {entry.header.note}")
    if entry.header.status in ("partial", "not-handled") and (now := today(entry, catalog.reference, levels)):
        bullets.append(f"**Today:** {now}.")
    if future := future_line(entry):
        bullets.append(f"**Future:** {future}")
    if blender := in_blender(entry):
        bullets.append(f"**Checked in Blender:** {blender}")
    notes = []
    for key, differs in differ.items():
        if differs:
            generator, version = key.split("/", 1)
            note = entry.header.differs.get(key) or topics.differs.get(key, "")
            notes.append(f"{generator} stubs, Blender {version}: {note}")
    if notes:
        bullets.append("**With other stubs:** " + " · ".join(notes))
    if not entry.checked:
        bullets.append(
            "**Not machine-checked:** the code is type-checked, so its API names exist, but nothing in it is asserted."
        )
    bullets.append(f"**More:** {more_links(entry)}")
    out += [f"- {b}" for b in bullets]
    return [*out, ""]


@dataclass
class Catalog:
    """Everything the pages are written from."""

    topics: Topics
    entries: list[Entry]
    reference: Recorded
    levels: dict[str, str]
    differ: dict[str, dict[str, bool]]  # entry id -> other generator/version -> differs

    def of_topic(self, topic: str) -> list[Entry]:
        return [e for e in self.entries if e.topic == topic]

    def of_section(self, topic: str, section: str) -> list[Entry]:
        return [e for e in self.entries if e.topic == topic and e.header.section == section]


def counts(entries: list[Entry]) -> list[str]:
    return [str(sum(e.header.status == s for e in entries) or "") for s in STATUSES]


def topic_page(catalog: Catalog, topic: Topic) -> str:
    out = [f"# {topic.title}", "", GENERATED_NOTE, "", topic.intro.strip(), ""]
    out += [
        "[All topics](README.md) · [Reading an entry](README.md#reading-an-entry) · [By safeguard](by-safeguard.md) · [Roadmap](roadmap.md)",
        "",
    ]
    out += [" · ".join(f"[{s.title}](#{s.id})" for s in topic.sections), ""]
    for section in topic.sections:
        out += [f'<a id="{section.id}"></a>', f"## {section.title}", ""]
        entries = catalog.of_section(topic.id, section.id)
        for entry in entries:
            out += render_entry(entry, catalog)
        if section.to_come:
            out += ["To come in this section: " + "; ".join(section.to_come) + ".", ""]
        elif not entries:
            out += ["Nothing here yet.", ""]
    return "\n".join(out).rstrip("\n") + "\n"


def index_line(entry: Entry) -> str:
    status = STATUSES.get(entry.header.status, entry.header.status).lower()
    return f"- [{entry.header.title}]({entry.topic}.md#{entry.anchor}) ({status}): {first_sentence(entry.prose)}"


# The legend on the index page, one bullet per line.
READING = """\
<a id="reading-an-entry"></a>
## Reading an entry

- **Status**: *Handled* (something deals with it for you), *Partial*, *Not handled* (with what can change: planned, \
possible, not statically checkable, out of scope; see the [roadmap](roadmap.md)) or *Unknown* (not classified yet). \
*To come* counts the entries a topic still lacks: their titles are listed on its page.
- **checked with Blender main, builtin stubs**: the example was type-checked by ty-blender against the stubs Blender \
itself generates for its development version. *Not machine-checked* entries make no claim a type checker could test.
- **Code**: `assert_type(x, T)` (from `typing`) states the type you get for `x`; `# reported: rule` marks a line \
ty-blender reports under that rule; `# not handled yet: why` marks the line that still goes wrong.
- **Script or add-on**: an example is a plain script unless it needs an add-on (registration checks, preferences, \
metadata): then it has a `bl_info` or a `blender_manifest.toml`, and its `register()` is what Blender calls. A script's \
classes are not checked for registration.
- **What you see**: the types and diagnostics those lines show, with each rule's default level (`error`, `warn`) \
linked to its description. **Today** says what is reported on a line not handled yet, **Future** what would handle it.
- **Checked in Blender**: what loading the example in Blender showed (`mise run check:load main --catalog`).
- **With other stubs**: where fake-bpy-module's stubs or Blender 5.2 give another result, and why.
- **More**: the project's own tests for the feature, Blender's documentation, and the example's source.
- Capitalised terms such as *Property host*, *Value type* or *Assumption* are defined in the \
[glossary](../../GLOSSARY.md).\
""".splitlines()


def index_page(catalog: Catalog) -> str:
    rows = []
    for topic in catalog.topics.topics:
        entries = catalog.of_topic(topic.id)
        to_come = sum(len(s.to_come) for s in topic.sections)
        rows.append([f"[{topic.title}]({topic.id}.md)", topic.covers, *counts(entries), str(to_come or "")])
    out = ["# Blender Python feature catalog", "", GENERATED_NOTE, "", catalog.topics.intro.strip(), ""]
    out += ["[By safeguard](by-safeguard.md) · [Roadmap](roadmap.md)", ""]
    out += table(["Topic", "Covers", *STATUSES.values(), "To come"], rows)
    out += ["", *READING]
    for topic in catalog.topics.topics:
        entries = catalog.of_topic(topic.id)
        out += ["", f"## [{topic.title}]({topic.id}.md)", ""]
        out += [index_line(e) for e in entries] or ["Nothing here yet."]
    return "\n".join(out) + "\n"


def safeguard_page(catalog: Catalog) -> str:
    out = [
        "# By safeguard",
        "",
        GENERATED_NOTE,
        "",
        "What deals with each entry of the catalog for you, and what each safeguard is.",
        "",
    ]
    out += ["[All topics](README.md) · [Roadmap](roadmap.md)", ""]
    for safeguard in SAFEGUARDS:
        info = catalog.topics.safeguards.get(safeguard, {})
        out += [
            f'<a id="{safeguard}"></a>',
            f"## {info.get('title', safeguard)}",
            "",
            info.get("description", "").strip(),
            "",
        ]
        entries = [e for e in catalog.entries if safeguard in e.header.safeguards]
        out += [index_line(e) for e in entries] or ["No entry yet."]
        out.append("")
    unhandled = [e for e in catalog.entries if not e.header.safeguards]
    out += ['<a id="not-handled"></a>', "## Nothing", "", "Entries nothing handles yet, or not classified yet.", ""]
    out += [index_line(e) for e in unhandled] or ["No entry."]
    return "\n".join(out).rstrip("\n") + "\n"


def roadmap_page(catalog: Catalog) -> str:
    out = [
        "# Roadmap",
        "",
        GENERATED_NOTE,
        "",
        "Everything the catalog says is not handled or handled in part, by what can change.",
        "",
    ]
    out += ["[All topics](README.md) · [By safeguard](by-safeguard.md)", ""]
    for cls, title in CLASSES.items():
        entries = [e for e in catalog.entries if e.header.future.get("class") == cls]
        out += [f'<a id="{cls}"></a>', f"## {title}", "", catalog.topics.classes.get(cls, "").strip(), ""]
        out += [f"{index_line(e)} *{e.header.future.get('note', '')}*" for e in entries] or ["No entry yet."]
        out.append("")
    partial = [e for e in catalog.entries if e.header.status == "partial" and not e.header.future]
    out += ['<a id="partial"></a>', "## Handled in part", "", "Partial entries without a class: what is missing.", ""]
    out += [f"{index_line(e)} *{e.header.note}*" for e in partial] or ["No entry yet."]
    out.append("")
    unknown = [e for e in catalog.entries if e.header.status == "unknown"]
    out += ['<a id="unknown"></a>', "## Not classified yet", ""]
    out += [index_line(e) for e in unknown] or ["No entry."]
    return "\n".join(out).rstrip("\n") + "\n"


def pages(catalog: Catalog) -> dict[str, str]:
    """Every page of ``docs/catalog/`` by file name."""
    files = {
        "README.md": index_page(catalog),
        "by-safeguard.md": safeguard_page(catalog),
        "roadmap.md": roadmap_page(catalog),
    }
    for topic in catalog.topics.topics:
        files[f"{topic.id}.md"] = topic_page(catalog, topic)
    return files


def catalog_problems(catalog: Catalog) -> list[str]:
    """What is wrong across entries: a stem used twice, or named like a module an entry may import (``enum.py``,
    ``bpy.py``), and an entry anchor that is also a section id."""
    problems = []
    stems: dict[str, Entry] = {}
    for entry in catalog.entries:
        if (other := stems.setdefault(entry.stem, entry)) is not entry:
            problems.append(f"{entry.main}: the file stem `{entry.stem}` is also {other.rel}: stems are unique")
    anchors = {s.id for t in catalog.topics.topics for s in t.sections}
    problems += [
        f"{e.main}: the anchor `{e.anchor}` is also a section id" for e in catalog.entries if e.anchor in anchors
    ]
    names = BLENDER_MODULES | set(sys.stdlib_module_names)
    problems += [
        f"{e.main}: the file stem `{e.stem}` is also a module name" for e in catalog.entries if e.stem in names
    ]
    return problems


def later_topics() -> set[str]:
    """The ``[later.*]`` topics of ``examples/addons/coverage.toml``."""
    data = tomllib.loads(COVERAGE_TOML.read_text(encoding="utf-8")) if COVERAGE_TOML.is_file() else {}
    return set(data.get("later", {}))
