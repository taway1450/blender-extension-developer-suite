# The catalog's entries

The source of [docs/catalog/](../../docs/catalog/README.md), the catalog of Blender-Python features for add-on
authors. Each Catalog entry is one checked example; the pages are generated from the entries and their recorded
results, so edit the entries, never the pages.

## Layout

```text
examples/catalog/
├── topics.toml             # topic order, titles, intros, sections, titles to come, safeguards, classes
├── ty.toml                 # marker rules; import roots written by catalog:generate
├── properties/             # a topic folder: one entry per file or package
│   └── scalar_types.py     # a script outside any add-on (the default form)
└── addons/
    └── own_preferences/    # an entry that needs an add-on: a package (with a manifest) or a module with bl_info
```

Every topic folder is an import root, so each entry is a top-level module, as Blender or a script runner loads it.
A script sees its own Registered properties and operators and no other entry's; an entry about registration
checks, preferences, `uses` or metadata takes the add-on form. File stems are unique across topics and never the
name of a module an entry may import (`enum.py`, `bpy.py`). The id of an entry is `<topic>/<stem with - for _>`;
it is also the anchor on its page.

## An entry

```python
# /// catalog
# title = "Enum items that unpack another tuple"
# section = "value-types"           # a section of the topic in topics.toml
# status = "not-handled"            # handled | partial | not-handled | unknown
# safeguards = []                   # stub-generator, runtime-probe, source-parser, typechecker,
#                                   # runtime-typechecker, blender-fix, linter-profile, blender-runtime
# features = ["properties"]         # feature-test directories, linked from the page
# later = "enum-items-unpacked"     # a [later.*] topic of examples/addons/coverage.toml
#
# [future]
# class = "planned"                 # planned | possible | not-checkable | out-of-scope
# note = "Read `*NAME` inside static `items` through the constant."
# tracked = "later/enum-items-unpacked"   # or remaining-causes/<id>, or #<issue>
# ///
"""Static `items` give the property a `Literal` Value type. When the sequence unpacks another one, the checker no
longer reads the identifiers."""

# catalog: hide
from typing import Literal, assert_type

# catalog: show
from bpy.props import EnumProperty
...


def example(settings: ExportSettings) -> None:
    # gap: the unpacked identifiers are not read
    assert_type(settings.file_format, Literal["SCENE", "OBJ", "STL"])
```

- **Header**: the `# /// catalog` TOML block (the PEP 723 comment form). Unknown keys are errors. A `handled` or
  `partial` entry names `safeguards`; `partial` says in `note` what is missing; `not-handled` has a `[future]`
  table with `class` and `note`, and `planned` also says where it is `tracked`. `unknown` means not classified yet.
  Other keys: `[evidence]` (a feature-test add-on whose `_expected/runtime.toml` shows a runtime claim, below),
  `blender-docs` (page names such as `info_gotcha` or `bpy.props`), `see` (paths in the Blender source, starting
  `blender/`), `[differs]` and `[runtime]` (below).
- **Prose**: the module docstring, in Markdown, in the terms of [GLOSSARY.md](../../GLOSSARY.md). Its first
  sentence is the entry's line in the indexes.
- **Markers**: the feature tests' own (`assert_type`, `# ty: ignore[rule]`, see
  [tests/typecheck/README.md](../../tests/typecheck/README.md)), plus the Gap tag: a `# gap: <reason>` comment line
  says the statement below it fails today. On the page `# ty: ignore[rule]` reads `# reported: rule` and a Gap tag
  `# not handled yet: reason`.
- **Shown code**: `# catalog: hide` and `# catalog: show` lines keep imports and helpers off the page. A shown part
  indented deeper than the hide line before it is dedented by the difference; prefer a visible `example()` function
  over a hidden wrapper, so the page shows where the names come from.
- **No checkable claim** (something only Blender at runtime decides): illustration code without markers. It is
  still type-checked, so its API names stay real, and its page says "not machine-checked".

## What is checked

`mise run catalog:generate --check` (also run by `mise run test:scripts`) judges each entry against the results
`check:catalog` recorded for the builtin stubs of Blender main (`examples/expected/builtin/main.catalog.txt`):

1. every recorded result lies in a Gap-tagged statement;
2. every Gap-tagged statement still fails; otherwise "the gap holds now: remove the tag and review `status`";
3. the status agrees: `handled` by a static safeguard (all but `linter-profile` and `blender-runtime`) has a marker and
   no Gap tag, `partial` has a marker that holds and a Gap tag, `not-handled` `planned` or `possible` has a Gap tag;
4. the entry was recorded as its code is now (the `checked` line holds a hash of the code without the header);
5. where another recorded generator or version (fake-bpy-module on main, both generators on 5.2) gives another
   outcome, the entry says why in `[differs]` (`"builtin/5.2" = "why"`), and a note without a difference is stale;
6. the header names only what exists (its `[evidence]` says what the add-on's `_expected/runtime.toml` records; the
   Blender docs pages and source paths exist at the pinned Blender commit, checked only when the `blender`
   submodule has it, as CI does), and the pages and `ty.toml`'s roots are current.

## Runtime claims

An entry that says what Blender does at runtime (rejects a declaration, keeps a value) shows evidence: a feature-test
add-on in an `[evidence]` table, or a `[runtime]` table with the keys of `_expected/runtime.toml` (`register`, `error`, `reason`,
`[[runtime.probe]]`), which makes it an add-on-form entry that `mise run check:load main --catalog` loads in Blender,
or Blender's docs or source in `blender-docs` / `see`. `blender-runtime` in `safeguards` needs `[evidence]` or a
`[runtime]` table. A claim with none of these is left out.

`[evidence]` names the feature-test add-on (`addon = "properties/props_defaults"`), what it records for registration
(`register = "fails"`, `ok` when left out) and, in `says`, a phrase its `reason` or `error` must contain; the check
fails when the add-on's `_expected/runtime.toml` says otherwise.

## Workflow

```sh
mise run check:catalog main properties      # type-check a topic (or topic/entry); read the summary
mise run check:catalog main properties --update
mise run check:catalog 5.2 properties --update
mise run check:load main --catalog          # the entries with a [runtime] table
mise run catalog:generate                   # judge every entry and write docs/catalog/
```
