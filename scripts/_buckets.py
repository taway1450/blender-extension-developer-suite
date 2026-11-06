"""Sort check:blender's diagnostics into root-cause buckets and areas of the Blender source.

``bucket(rule, msg, text)`` applies a first-match rule table to a diagnostic's rule, message and the source line it
points at (read from the worktree ty just checked, so message and line always belong together). ``area(path)``
names the part of the source tree a path is in. The table comes from the check:blender setup research
(``docs/research/check-blender-setup.md`` on the ``research/check-blender-setup`` branch).
"""

from __future__ import annotations

import collections
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# In report order: one row per bucket in the summary, also when zero.
BUCKETS = [
    "context-member",
    "pointer-none",
    "type-tag",
    "stub-gap",
    "operator-call",
    "check-setup",
    "dynamic",
    "rest",
]

DIAGNOSTIC_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):\d+: \w+\[(?P<rule>[\w-]+)\] (?P<msg>.*)$", re.MULTILINE
)

SETUP_RULES = {"import-not-found", "unresolved-import", "possibly-missing-submodule"}
STUB_GAP_RULES = {
    "not-iterable",
    "unsupported-operator",
    "not-subscriptable",
    "invalid-method-override",
    "invalid-attribute-override",
    "invalid-property-type-override",
    "invalid-mutable-override",
}

# Cycles' Registered properties, assigned in a `PropertyGroup.register()` classmethod the register() walk doesn't run.
CYCLES_PROPERTY = re.compile(r"^Object of type `.*` has no attribute `cycles\w*`")
STRING_LITERAL = re.compile(r"""['"]""")
ID_TYPE = re.compile(r"`ID( \| None)?`")
NULLABLE = re.compile(r"\| None`|`None \||in union `[^`]*None")
# The attribute a nullable message is about.
NULLABLE_ATTRIBUTE = re.compile(r"Attribute `(\w+)` is not defined on|has no attribute `(\w+)`|to attribute `(\w+)`")
CONTEXT = r"\b(?:context|ctx|C|_context)\."
CONTEXT_TYPE = re.compile(
    r"`(?:Scene|ViewLayer|WindowManager|Preferences|ToolSettings|Space|Region|Area|Screen|Window|WorkSpace|Context)"
    r" \| None`"
)
SETTINGS_POINTER = re.compile(
    r"(?:Domain|Flow|Effector)Settings|RigidBody\w*|FieldSettings|ParticleSettings|Brush\w*Settings|SceneEEVEE"
)
BASE_CLASS = re.compile(r"`(?:NodeSocket|Node|Constraint|Modifier|Strip|ActionStrip|Light|Curve|Texture|Space|ID)`")
MODULE_MEMBER = re.compile(r"Module `[\w.]+` has no member")

AREAS = [
    (
        "shipped",
        (
            "scripts/startup/",
            "scripts/modules/",
            "scripts/addons_core/",
            "scripts/freestyle/",
            "intern/cycles/blender/addon/",
        ),
    ),
    ("presets", ("scripts/presets/",)),
]
AREA_NAMES = [name for name, _ in AREAS] + ["other"]


def bucket(rule: str, msg: str, text: str) -> str:
    """The bucket of a diagnostic with ``rule`` and message ``msg`` on the source line ``text``."""
    if rule in SETUP_RULES or "Cannot resolve imported" in msg or CYCLES_PROPERTY.search(msg):
        return "check-setup"
    if "Self@" in msg or "ToolDef" in msg:
        return "dynamic"
    if (
        "bpy.ops." in text
        or "OperatorProperties" in msg
        or (rule == "too-many-positional-arguments" and STRING_LITERAL.search(text))
    ):
        return "operator-call"
    if ID_TYPE.search(msg) and "data" in text:
        return "type-tag"
    if NULLABLE.search(msg):
        if is_context_member(msg, text):
            return "context-member"
        if SETTINGS_POINTER.search(msg):
            return "type-tag"
        return "pointer-none"
    if rule == "unresolved-attribute" and BASE_CLASS.search(msg):
        return "type-tag"
    if (
        rule in STUB_GAP_RULES
        or "bl_rna" in msg
        or "object.__init__" in msg
        or MODULE_MEMBER.search(msg)
    ):
        return "stub-gap"
    return "rest"


def is_context_member(msg: str, text: str) -> bool:
    """Whether a nullable diagnostic comes from a context member: its attribute follows a context member on the
    line (``context.scene.render``), the nullable type is one of the context's own, or an ``Object | None`` read on a
    line that reads the context."""
    attribute = NULLABLE_ATTRIBUTE.search(msg)
    if attribute:
        name = next(group for group in attribute.groups() if group)
        if re.search(CONTEXT + r"\w+\." + re.escape(name) + r"\b", text):
            return True
    if CONTEXT_TYPE.search(msg):
        return True
    return "`Object | None`" in msg and re.search(CONTEXT + r"\w+", text) is not None


@dataclass(frozen=True)
class Diagnostic:
    path: str  # relative to the source root, as ty prints it
    line: int
    rule: str
    msg: str
    text: str  # the source line

    @property
    def bucket(self) -> str:
        return bucket(self.rule, self.msg, self.text)

    @property
    def area(self) -> str:
        return area(self.path)


def read_diagnostics(output: str, source: Path) -> list[Diagnostic]:
    """The diagnostics of ty's concise ``output``, run in ``source``, each with the source line it points at."""
    files: dict[str, list[str]] = {}
    diagnostics = []
    for match in DIAGNOSTIC_LINE.finditer(output):
        path, line = match["path"], int(match["line"])
        if path not in files:
            try:
                files[path] = (source / path.replace("\\", "/")).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                files[path] = []
        lines = files[path]
        text = lines[line - 1] if 0 < line <= len(lines) else ""
        diagnostics.append(Diagnostic(path, line, match["rule"], match["msg"], text))
    return diagnostics


def samples(diagnostics: list[Diagnostic], per_bucket: int = 20) -> str:
    """The first ``per_bucket`` diagnostics of each bucket with their source line, for reading."""
    by_bucket: dict[str, list[Diagnostic]] = collections.defaultdict(list)
    for d in diagnostics:
        by_bucket[d.bucket].append(d)
    out = []
    for name in BUCKETS:
        out.append(f"## {name} ({len(by_bucket[name])})\n")
        for d in by_bucket[name][:per_bucket]:
            out.append(f"{d.path}:{d.line}: [{d.rule}] {d.msg}\n    | {d.text.strip()}\n")
        out.append("\n")
    return "".join(out)


def summary(title: str, diagnostics: Iterable[tuple[str, str, str]]) -> str:
    """The bucket × area table and the counts per rule (sorted by name) of ``diagnostics``, given as (bucket, area,
    rule). Every bucket gets a row, also when zero, so a diff of two summaries shows what moved where."""
    diagnostics = list(diagnostics)
    cells = collections.Counter((b, a) for b, a, _ in diagnostics)
    rules = collections.Counter(rule for _, _, rule in diagnostics)

    def row(name: str, counts: list[int]) -> str:
        return f"{name:<16}" + "".join(f"{n:>9}" for n in counts) + "\n"

    lines = [title + "\n", f"{'bucket':<16}" + "".join(f"{a:>9}" for a in [*AREA_NAMES, "total"]) + "\n"]
    for name in BUCKETS:
        counts = [cells[name, a] for a in AREA_NAMES]
        lines.append(row(name, [*counts, sum(counts)]))
    totals = [sum(cells[b, a] for b in BUCKETS) for a in AREA_NAMES]
    lines.append(row("total", [*totals, sum(totals)]))
    lines.append("\n")
    lines.append(f"{'rule':<36}{'count':>6}\n")
    lines.extend(f"{rule:<36}{rules[rule]:>6}\n" for rule in sorted(rules))
    return "".join(lines)


def area(path: str) -> str:
    """The area of a path relative to the Blender source root (``/`` or ``\\`` separated)."""
    path = path.replace("\\", "/")
    for name, prefixes in AREAS:
        if path.startswith(prefixes):
            return name
    return "other"
