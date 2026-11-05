"""The marker grammar of the feature tests: what a ``check_*.py`` or ``ide_*.py`` file asks of the checker.

One parser for every marker kind, used by ``check:features``, ``check:oracle`` and ``check:ide``. It works on a file's
text and its path (relative to tests/typecheck), so it never reads files. The syntax is described in
``tests/typecheck/README.md``.

Every marker has a ``key`` that names its line by content rather than by number (see ``line_keys``). The recorded
results use it, so moving code around does not change them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from _common import StepError

CHECK_PREFIX = "check_"  # type markers that check:oracle also judges
IDE_PREFIX = "ide_"  # editor markers for check:ide; check:features ignores these files

ASSERT_TYPE = re.compile(r"\bassert_type\(")
EXPECTED_ERROR = re.compile(r"#\s*ty:\s*ignore\[(?P<rules>[^\]]+)\]")
ORACLE_SKIP = re.compile(r"#\s*oracle-skip\b")
BARE_OK = re.compile(r"#\s*bare-ok\b(?P<reason>:\s*\S)?")
IDE_MARKER = re.compile(r"^\s*#.*?\^(?P<kind>[a-z][a-z-]*)(?:\s+(?P<arg>.*?))?\s*$")
IDE_KINDS = ("hover", "hover-contains", "hover-none", "signature", "signature-param", "completion", "deprecated")
RECORDING_IDE_KINDS = ("hover", "signature")

ASSERT = "assert_type"
EXPECTED = "expected-error"
ASSERT_FAILURE = "type-assertion-failure"
UNUSED_IGNORE = "unused-ignore-comment"
# Rules that only ty-blender reports. Until it does, ty flags their ignore comments as unknown rules.
BLENDER_RULE_PREFIX = "blender-"
UNKNOWN_RULE = "ignore-comment-unknown-rule"


class MarkerError(StepError):
    """A marker that cannot be parsed; the message starts with ``path:line``."""


def file_name(path: str) -> str:
    return path.rpartition("/")[2]


def is_check_file(path: str) -> bool:
    return file_name(path).startswith(CHECK_PREFIX)


def is_ide_file(path: str) -> bool:
    return file_name(path).startswith(IDE_PREFIX)


def line_keys(lines: list[str]) -> list[str]:
    """A key per line: its stripped text, with `` #2``, `` #3`` ... on the later lines that have the same text.

    The key of a line stays the same when other lines are added, removed or moved, unless they have the same text
    and come before it.
    """
    seen: dict[str, int] = {}
    keys = []
    for line in lines:
        text = line.strip()
        count = seen[text] = seen.get(text, 0) + 1
        keys.append(text if count == 1 else f"{text} #{count}")
    return keys


# --- type markers (check_*.py and the add-on's own modules) -----------------------------------------------------------


@dataclass(frozen=True)
class TypeMarker:
    path: str  # relative to tests/typecheck, with forward slashes
    line: int  # 1-based
    kind: str  # ASSERT or EXPECTED
    source: str  # the stripped line
    key: str  # the line's key (``line_keys``)
    rules: tuple[str, ...] = ()  # the rules of an expected error
    oracle_skip: bool = False
    bare_ok: bool = False  # a guard: meant to hold without ty-blender, so the bare run does not flag it

    @property
    def failure_rules(self) -> tuple[str, ...]:
        """The rules ty reports on the line when the marker fails. The first one is the usual one."""
        if self.kind == ASSERT:
            return (ASSERT_FAILURE,)
        # A rule ty does not know yet (a blender-* rule before ty-blender reports it) is an expected error that is
        # not found either.
        return (UNUSED_IGNORE, UNKNOWN_RULE)

    @property
    def blender_only(self) -> bool:
        """An expected error that only ty-blender can report: stock ty with reference stubs cannot."""
        return self.kind == EXPECTED and all(r.startswith(BLENDER_RULE_PREFIX) for r in self.rules)

    @property
    def in_check_file(self) -> bool:
        return is_check_file(self.path)

    @property
    def needs_checker(self) -> bool:
        """Whether the marker claims to need ty-blender, so that the bare run (stock ty on the bare stubs) must fail
        it. Guards (``# bare-ok``) do not, and neither do ``blender-*``-only expected errors: stock ty cannot report
        those at all."""
        return not self.bare_ok and not self.blender_only


@dataclass(frozen=True)
class TypeFile:
    """The type markers of one file and its ``# oracle-skip`` lines (which may hold no marker)."""

    markers: list[TypeMarker]
    oracle_skip_lines: frozenset[int]  # 1-based
    keys: list[str]  # line_keys of the file; keys[line - 1]


def parse_type_file(path: str, text: str) -> TypeFile:
    """The ``assert_type`` and ``# ty: ignore[...]`` markers of a file.

    A line with an ignore comment is an expected error even when it also calls ``assert_type``. ``assert_type`` in
    a comment or an import line is not a marker. ``# bare-ok: <reason>`` must give a reason and be on a marker line,
    but not on a ``blender-*``-only expected error.
    """
    lines = text.splitlines()
    keys = line_keys(lines)
    markers = []
    skipped = set()
    for number, line in enumerate(lines, start=1):
        skip = ORACLE_SKIP.search(line) is not None
        if skip:
            skipped.add(number)
        bare_ok = BARE_OK.search(line)
        if bare_ok and not bare_ok["reason"]:
            raise MarkerError(f"{path}:{number}: # bare-ok needs a reason (# bare-ok: <reason>)")
        source, key = line.strip(), keys[number - 1]
        if match := EXPECTED_ERROR.search(line):
            rules = tuple(r.strip() for r in match["rules"].split(","))
            marker = TypeMarker(path, number, EXPECTED, source, key, rules, skip, bool(bare_ok))
        elif ASSERT_TYPE.search(line) and not line.lstrip().startswith(("#", "from ", "import ")):
            marker = TypeMarker(path, number, ASSERT, source, key, oracle_skip=skip, bare_ok=bool(bare_ok))
        elif bare_ok:
            raise MarkerError(f"{path}:{number}: # bare-ok on a line without a marker")
        else:
            continue
        if marker.bare_ok and marker.blender_only:
            raise MarkerError(f"{path}:{number}: # bare-ok on an expected error that only ty-blender can report")
        markers.append(marker)
    return TypeFile(markers, frozenset(skipped), keys)


# --- editor markers (ide_*.py) ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class IdeMarker:
    path: str  # relative to tests/typecheck, with forward slashes
    line: int  # 0-based line of the queried code (LSP positions are 0-based)
    character: int  # 0-based column of the caret
    kind: str
    arg: str | None
    source: str  # the stripped queried line
    key: str  # the queried line's key (``line_keys``)

    @property
    def title(self) -> str:
        """Names the marker in the recorded results, without the line number."""
        arg = f" {self.arg}" if self.arg else ""
        return f"{self.path} | ^{self.kind}{arg} @{self.character + 1} | {self.key}"

    @property
    def asserts(self) -> bool:
        """Whether the marker can fail. ``^hover`` and ``^signature`` only record what the server returns."""
        return self.kind not in RECORDING_IDE_KINDS

    def quoted_arg(self) -> str:
        """The marker's argument without its quotes (``^hover-contains "text"``)."""
        arg = self.arg
        if not arg or not (len(arg) >= 2 and arg[0] == arg[-1] == '"'):
            raise MarkerError(f"{self.path}:{self.line + 1}: expected a quoted string after ^{self.kind}, got {arg!r}")
        return arg[1:-1]


def parse_ide_file(path: str, text: str) -> list[IdeMarker]:
    """The caret markers of an ``ide_*.py`` file. Each queries the nearest code line above it."""
    if not text.isascii():
        # LSP positions count UTF-16 code units; with ASCII they equal the column of the caret.
        raise MarkerError(f"{path}: contains non-ASCII characters; IDE test files must be ASCII")
    lines = text.splitlines()
    keys = line_keys(lines)
    markers = []
    target = None
    for number, line in enumerate(lines):
        match = IDE_MARKER.match(line)
        if match is None:
            if line.strip() and not line.lstrip().startswith("#"):
                target = number
            continue
        if match["kind"] not in IDE_KINDS:
            raise MarkerError(f"{path}:{number + 1}: unknown marker ^{match['kind']} (known: {', '.join(IDE_KINDS)})")
        if target is None:
            raise MarkerError(f"{path}:{number + 1}: marker without a code line above it")
        markers.append(
            IdeMarker(path, target, line.index("^"), match["kind"], match["arg"], lines[target].strip(), keys[target])
        )
    titles = [m.title for m in markers]
    if duplicate := next((t for t in titles if titles.count(t) > 1), None):
        raise MarkerError(f"{path}: two markers have the same title {duplicate!r}")
    return markers
