# /// script
# requires-python = ">=3.12"
# ///
"""Judge the catalog entries in ``examples/catalog/`` and write their pages in ``docs/catalog/``.

Every entry is judged against the results ``check:catalog`` recorded for the builtin stubs of Blender main
(``examples/expected/builtin/main.catalog.txt``), without running ty (``_catalog.verdict``): no result outside a Gap
tag, no Gap tag that holds, a status that agrees with the markers, and an entry recorded as its code is now. A result
that differs with another recorded stub generator or Blender version needs a ``[differs]`` note. The header must
name only what exists (its section in ``topics.toml``, features, ``later`` topics, trackers, evidence).

The pages are one per topic, an index, a page by safeguard and a roadmap. The import roots in
``examples/catalog/ty.toml`` (one per topic folder) are written too.

``--check`` writes nothing and fails when an entry does not hold or a page is out of date.

Usage:
  uv run scripts/generate_catalog.py           # write
  uv run scripts/generate_catalog.py --check   # compare only
"""

from __future__ import annotations

import argparse

from _catalog import (
    ANY_RULE_HEADING,
    OTHERS,
    PAGES_DIR,
    REFERENCE,
    TOPICS_TOML,
    TY_TOML,
    Catalog,
    blender_commit,
    catalog_problems,
    code_hash,
    differences,
    differs_problems,
    header_problems,
    later_topics,
    leftover_lines,
    load_entry,
    pages,
    read_recorded,
    read_topics,
    recorded_file,
    stale_recordings,
    verdict,
)
from _common import REPO_ROOT, StepError, log, main_wrapper
from _features import catalog_entry_list, feature_names, import_roots
from examples_coverage import RULES_MD, read_rules
from generate_features import updated_ty_toml

ROOTS_BEGIN = "# BEGIN generated roots (scripts/generate_catalog.py)"


def current() -> tuple[Catalog, list[str], str]:
    """The catalog as the repository has it, what is wrong with it, and ty.toml with the current roots."""
    if not RULES_MD.is_file():
        raise StepError(f"{RULES_MD} is missing: check out the ty-blender submodule with its ruff-blender submodule")
    addons = catalog_entry_list([])
    topics = read_topics(TOPICS_TOML.read_text(encoding="utf-8"))
    reference = read_recorded(recorded_file(*REFERENCE))
    others = {key: read_recorded(recorded_file(*key)) for key in OTHERS}
    features, later = feature_names(), later_topics()
    entries, problems, differ = [], list(topics.problems), {}
    for addon in addons:
        entry = load_entry(addon)
        entries.append(entry)
        problems += entry.problems + header_problems(entry, topics, features, later)
        problems += verdict(entry, reference, code_hash(addon))
        found = differences(entry, reference, others)
        problems += stale_recordings(entry, reference, others) + differs_problems(entry, found, topics.differs)
        differ[entry.id] = found
    catalog = Catalog(topics, entries, reference, read_rules(RULES_MD, ANY_RULE_HEADING), differ)
    problems += catalog_problems(catalog)
    files = {"/".join(key): record for key, record in [(REFERENCE, reference), *others.items()]}
    problems += leftover_lines(entries, files)
    ty_toml = updated_ty_toml(TY_TOML.read_text(encoding="utf-8"), import_roots(addons), ROOTS_BEGIN, TY_TOML)
    return catalog, problems, ty_toml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Fail if an entry does not hold or a page is stale")
    args = parser.parse_args()

    catalog, problems, ty_toml = current()
    if blender_commit() is None:
        log("The blender submodule lacks its pinned commit: Blender docs pages and source paths are not checked")
    for problem in problems:
        print(f"    {problem}", flush=True)
    files = {PAGES_DIR / name: text for name, text in pages(catalog).items()}
    files[TY_TOML] = ty_toml
    existing = {p for p in PAGES_DIR.glob("*.md")} if PAGES_DIR.is_dir() else set()
    stale = existing - set(files)
    changed = [p for p, text in files.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
    summary = f"{len(catalog.entries)} entries in {len(catalog.topics.topics)} topics"

    if args.check:
        for path in [*changed, *sorted(stale)]:
            print(f"    out of date: {path.relative_to(REPO_ROOT).as_posix()}", flush=True)
        if changed or stale:
            log("The catalog pages are out of date; run `mise run catalog:generate`")
        if problems or changed or stale:
            return 1
        log(f"Up to date: {summary}")
        return 0

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    for path in changed:
        path.write_text(files[path], encoding="utf-8", newline="\n")
        log(f"Wrote {path.relative_to(REPO_ROOT).as_posix()}")
    for path in stale:
        path.unlink()
        log(f"Removed {path.relative_to(REPO_ROOT).as_posix()}")
    log(summary)
    return 1 if problems else 0


if __name__ == "__main__":
    main_wrapper(main)
