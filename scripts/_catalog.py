"""The catalog of Blender-Python features in ``examples/catalog/``: its entries, their headers, and the verdict.

Each entry is a ``.py`` file (or a package directory) in a topic folder, with a ``# /// catalog`` TOML header, a
module docstring as its prose and checked code (see ``examples/catalog/README.md``). ``check_addons.py --catalog``
type-checks the entries and records the results; ``generate_catalog.py`` reads them back, judges every entry and
writes the pages in ``docs/catalog/``.
"""

from __future__ import annotations

import hashlib
import re

from _baseline import SEPARATOR, entry_path, type_entry
from _features import Addon

HEADER_START = "# /// catalog"
HEADER_END = "# ///"
CHECKED = "checked"  # the rule column of an entry's ``checked`` line in the recorded results
HASH_LENGTH = 12


def split_header(text: str) -> tuple[list[str], list[str]]:
    """The lines of the ``# /// catalog`` block (without its fences) and every other line, in order. No block gives
    an empty header."""
    lines = text.splitlines()
    header: list[str] = []
    for start, line in enumerate(lines):
        if line.rstrip() == HEADER_START:
            for end in range(start + 1, len(lines)):
                if lines[end].rstrip() == HEADER_END:
                    return lines[start + 1 : end], lines[:start] + lines[end + 1 :]
            break
    return header, lines


def code_hash(entry: Addon) -> str:
    """A short hash of the entry's code: every Python file without its header, so editing only the header (its
    status, its notes) does not ask for another ``check:catalog`` run."""
    digest = hashlib.sha256()
    for path in entry.python_files():
        _, code = split_header(path.read_text(encoding="utf-8"))
        digest.update(path.relative_to(entry.path.parent).as_posix().encode())
        digest.update(b"\0" + "\n".join(code).encode() + b"\0")
    return digest.hexdigest()[:HASH_LENGTH]


def checked_line(entry: Addon) -> str:
    """The recorded line that says the entry was checked as its code is now: ``path | checked | hash``."""
    return type_entry(entry.rel, CHECKED, code_hash(entry))


def checked_entries(entries: list[Addon], results: dict[str, str]) -> dict[str, str]:
    """A run's results with each entry's ``checked`` line before its own results."""
    lines = {checked_line(entry): "" for entry in entries}
    merged = {**lines, **results}
    order = {key: index for index, key in enumerate(merged)}
    return {key: merged[key] for key in sorted(merged, key=lambda key: (owner(key, entries), order[key]))}


def owner(key: str, entries: list[Addon]) -> str:
    """The path of the entry a recorded line belongs to (its own path when none does)."""
    path = entry_path(key)
    return next((entry.rel for entry in entries if entry.contains(path)), path)


CHECKED_LINE = re.compile(rf"^(?P<path>.+?){re.escape(SEPARATOR)}{CHECKED}{re.escape(SEPARATOR)}(?P<hash>[0-9a-f]+)$")
