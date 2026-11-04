# Testing what the editor shows: hover, signature help, completions and docstrings

Research note, 2026-11-04. It follows on from [typecheck-test-addons.md](typecheck-test-addons.md), which
covers testing *types* with `assert_type` and `# ty: ignore[...]`. The question here was: "what if I wanted
the hover information and docstrings, not just type?" In other words, how do we test what a user of the
stubs sees in the editor: hover text, signature help, completion documentation, docstrings on classes,
functions, properties and enum items, and deprecation notices.

Conventions are the same as in the earlier note:

- Every fact has a source next to it, either a URL or a `path:line` in this repo or its submodules.
- My own recommendations are marked **Recommendation** or written as "I recommend".
- *Verified locally* means the output came from this repo's ty build
  (`ty-blender/ruff/target/release/ty.exe`, `ty 0.0.95 (48c5ea1ba 2026-10-29)`), driven over stdio by a
  ~100-line Python LSP client in a temp directory (since deleted). The stubs were `.cache/bpy-stubs/5.2`
  and `.cache/bpy-stubs/main` (fake-bpy-module) and `.cache/bpy-stubs-builtin/main` (Blender's generator),
  with `python-version = "3.13"` and `extra-paths` set in a `ty.toml`.

---

## 1. Summary

1. **There is no CLI for hover output.** `ty` has only `check`, `server`, `version` and `explain`
   (*verified locally*, `ty --help`). Testing what the editor shows means talking LSP to `ty server`.
   A minimal stdio client is enough: 12 hovers took 0.28 s and 671 hovers took 0.41 s, and two runs gave
   byte-identical results (*verified locally*).
2. **Blender's built-in stub generator emits no docstrings at all.** The generated `.pyi` files contain
   0 triple-quoted strings (*verified locally*, 143 files), and its data model has no field for prose
   (`blender/doc/python_api/sphinx_stub_gen.py:65-120`). With those stubs every hover is a bare type or
   signature, and signature help and completions carry no documentation (*verified locally*).
3. **fake-bpy-module emits RST-flavoured docstrings** for classes, functions, operators and most
   properties, and ty renders them. Several gaps are only visible in the editor:
   - **Parameter docs are lost in some functions.** In 934 of 14 961 functions with `:param`, mixed
     indentation leaves the `:param` lines indented after PEP 257 trimming. Examples are `Object.ray_cast`,
     `bpy.props.IntProperty` and every operator with enum parameters. ty then shows the `:param` lines
     as indented prose. They are missing from keyword-argument hover and from signature-help parameter
     documentation (§3.3).
   - **Enum item descriptions are `#` comments.** These are invisible to every LSP feature (§4.1).
   - **Deprecation runs into the description.** The note is concatenated without separators and loses the
     word "Deprecated", for example `...default 0.0)Automasking 'View Normal' should be used instead5.3
     removal planned in version 6.0` (§4.1).
4. **ty has gaps of its own:**
   - **Completion documentation for an attribute is the docstring of its type.** `location` shows
     Vector's class docstring, not "Location of the object" (`ty_ide/src/completion.rs:450-462`;
     *verified locally*).
   - **Hovering an enum string literal returns nothing** (`ty_ide/src/hover.rs:59-63`).
   - **Signature help is always plain text** (`ty_server/src/server/api/requests/signature_help.rs:116,133`).
   - **Completions never carry a deprecated tag** (§2.3).
5. **Recommendation:** add `# ^hover`-style caret markers to the same `tests/typecheck/features/` files the
   earlier note proposes. Snapshot the normalized hover, signature and completion text into golden files per
   generator and version. Then generate RNA-driven assertions such as "the RNA description of every
   property appears in its hover".

---

## 2. How hover and docstrings reach the editor in ty

### 2.1 The LSP side

- **Formats.** `MarkupContent` is `{kind: 'plaintext' | 'markdown', value}`. Markdown should follow GitHub
  Flavored Markdown
  (https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#markupContent).
- **Hover.** The client lists the formats it accepts in `HoverClientCapabilities.contentFormat`, and "the
  order describes the preferred format of the client". `Hover.contents` is a `MarkupContent` (the older
  `MarkedString` is deprecated). The optional `range` marks the text the hover applies to (same spec,
  `#textDocument_hover`).
- **Completion.**
  - `CompletionItem` has `detail` (type or symbol info), `documentation` (`string | MarkupContent`) and
    `tags`. `CompletionItemTag.Deprecated` renders the item struck out. The older `deprecated: boolean`
    is itself deprecated in favour of `tags`.
  - `completionItem/resolve` lets a server compute `detail` and `documentation` lazily if it advertises
    `CompletionOptions.resolveProvider`. Since 3.16 the client can list more lazily resolvable
    properties in `resolveSupport` (same spec, `#textDocument_completion`, `#completionItem_resolve`).
- **Signature help.** `SignatureInformation.documentation` and `ParameterInformation.documentation` are
  both `string | MarkupContent`. `ParameterInformation.label` is either a string or `[start, end)` offsets
  into the signature label (same spec, `#textDocument_signatureHelp`).
- **Deprecated diagnostics.** `DiagnosticTag.Deprecated` marks "deprecated or obsolete code". Clients may
  strike it through (same spec, `#diagnosticTag`).

### 2.2 Where ty finds a docstring

1. **The hover target.** `hover()` resolves the cursor to a "goto target" (`ty_ide/src/hover.rs:20-27`).
   Literal expressions return no hover at all (`hover.rs:59-63`). A call takes the docstring of the resolved
   signature's definition. If that has none, as for a constructor's `__init__`, it falls back to the
   goto-definition targets (`hover.rs:80-95`). Any other target uses the goto-definition targets'
   docstring (`hover.rs:96-104`). The hover is then built as signature, parameter or type, followed by the
   docstring, joined by a horizontal rule (`hover.rs:106-173, 333-348`).
2. **Keyword-argument hover** shows `(parameter) name: T = default`, plus that parameter's documentation
   taken from the function docstring's parsed parameter section (`hover.rs:251-303, 315-324`).
3. **Docstring lookup order.** ty first uses the definition's own docstring, for example the one in the
   `.pyi`. If there is none, it maps the stub definition to the "real" module, re-resolved with stubs
   disabled, and takes that docstring (`ty_ide/src/goto.rs:436-462`;
   `ty_python_semantic/src/types/ide_support.rs:1700-1760`). For overloads it also tries the
   implementation's docstring (`goto.rs:491-505`; `definition_resolution.rs:114-147`).
   **Consequence for bpy:** `bpy` is a C extension with no `.py` source, so the stub-to-source fallback
   finds nothing. **The stub docstring is the only source.** This is my inference from the mapping code,
   which needs a real module file (`ide_support.rs:1745-1749`).
4. **What counts as a docstring.** Functions, classes and modules use the first string statement in the
   body. Assignments and annotated assignments use an "attribute docstring": a string literal directly
   after the assignment (`ty_python_core/src/definition.rs:154-183, 229-260`). So all three fake-bpy-module
   forms work: `prop: T` + `"""doc"""`, a `@property` body docstring, and a class docstring
   (*verified locally*).
5. **typeshed precedent.** ty's vendored stdlib stubs are enriched with runtime docstrings by
   `docstring-adder` during every typeshed sync (`ty-blender/ruff/.github/workflows/sync_typeshed.yaml:9-18`;
   `ty-blender/ruff/scripts/codemod_docstrings.sh`). That is why hovering an `int` shows `int([x]) -> integer...`.

### 2.3 How ty renders it

- **Plain text or Markdown.** Plain text is the PEP 257-trimmed docstring. Markdown runs it through a
  structured renderer (`ty_ide/src/docstring.rs:29-35`; `docstring/markdown.rs:9-14`).
  - **Formats parsed.** The renderer parses Google, NumPy and reST/Sphinx docstrings
    (`docstring.rs:1-7`; `docstring/document/{google,numpy,rst}.rs`).
  - **reST fields.** `:param/:arg/:key`, `:type`, `:return(s)`, `:rtype`, `:raises`, `:ivar` and
    `:vartype` are recognized (`docstring/document/rst.rs:536-570`).
  - **Field lists must be top-level.** A field list only counts if it is at indent 0 after trimming and
    starts a block (`rst.rs:21-32`).
- **Sections in Markdown.** Recognized fields become `## Parameters` / `## Arguments` / `## Returns`
  sections, with `**name**: \`type\`` entries (snapshot in `hover.rs:705-752`, `hover.rs:593-648`).
- **Roles.** Inline roles such as ``:class:`pkg.Model` `` are reduced to their label (`docstring/markdown/structured.rs:392-430`).
- **Directives.** `.. note::`, `.. warning::`, `.. deprecated:: X` and similar admonitions become bold
  headings like `**Deprecated since version X:**` (`docstring/markdown/general.rs:152-235`).
  The parser only recognizes `.. name::` or `.. name:: <one word>`
  (`general.rs:153-162`). Blender writes `.. deprecated:: 5.1 removal planned in version 6.0`
  (`blender/doc/python_api/sphinx_doc_gen.py:2303-2316`), and *verified locally* that form is shown
  verbatim. `.. deprecated:: 5.1` alone renders as `**Deprecated since version 5.1:**`.
- **Markdown artefacts to normalize in tests.** Line breaks become `"  \n"` hard breaks. Leading
  indentation becomes `&nbsp;`. `<`, `>` and `_` are escaped (`&lt;`, `\_`) (*verified locally*).
  ty's own hover tests replace `"  \n"` with `<HB>\n` "so snapshot literals remain stable"
  (`hover.rs:515-522`).
- **Server-side choices:**
  - **Hover format.** Hover is Markdown if the client lists markdown first in `hover.contentFormat`,
    otherwise plain text (`ty_server/src/server/api/requests/hover.rs:55-63`; `ty_server/src/capabilities.rs:335-341`).
  - **Completion format.** Completion documentation follows `completionItem.documentationFormat` the same
    way (`capabilities.rs:343-352`; `requests/completion.rs:118-133`).
  - **Signature help is always plain text.** The signature documentation is
    `Documentation::String(render(PlainText))`. Parameter documentation is a plain string
    (`requests/signature_help.rs:116, 133`).
  - **No lazy resolve.** There is no `resolveProvider`: completion documentation is sent eagerly with
    every item (`capabilities.rs:520-523`; `requests/completion.rs:118-151`).
  - **Completion documentation comes from the type.** `Definitions::from_ty(semantic.ty)` is used for the
    item's documentation (`ty_ide/src/completion.rs:450-462`). For a method that is the method's
    docstring. For an attribute it is the docstring of the attribute's *type's* class.
    - *Verified locally:* `obj.locat` → `location` shows "This object gives access to Vectors in Blender."
    - *Verified locally:* a user property shows the explanation of `Unknown`.
- **Deprecation:**
  - **Diagnostics.** `@deprecated` produces a `deprecated` diagnostic with `DiagnosticTag::Deprecated`
    (`ty_server/src/server/api/diagnostics.rs:484`; *verified locally*: `warning[deprecated] The function
    \`old_method\` is deprecated: Use new_method instead`).
  - **Completions.** A deprecated symbol is only ranked lower (`completion.rs:525, 1910-1914`). No LSP
    `tags` are set on the item (`requests/completion.rs:141-156`).
  - **Hover.** The hover for a `@deprecated` method shows no deprecation text (*verified locally*).

### 2.4 How ty tests this itself

- **`ty_ide` cursor tests.** Sources are written with an inline `<CURSOR>` marker, removed before parsing
  (`ty_ide/src/lib.rs:425-430, 755-797`).
  - The hover helper snapshots the plain-text rendering, a separator, the Markdown rendering, and a
    diagnostic-style picture of the hovered range and cursor offset (`hover.rs:7429-7475`; example
    `hover.rs:524-562`).
  - Snapshots are `insta` inline snapshots.
  - Signature help (`signature_help.rs:1678`, `signature_help_render`) and completions
    (`completion.rs:11532, 11794`) use the same builder.
- **`ty_server` end-to-end tests.** A real server is driven with `hover_request`, `completion_request` and
  `signature_help_request` (`ty_server/tests/e2e/main.rs:1085, 1121, 1148`). JSON responses are snapshotted
  with `insta::assert_json_snapshot!` (`ty_server/tests/e2e/hover.rs:44-80`). Format negotiation has its
  own tests (`e2e/hover.rs:6-41`).
- **`ty_completion_eval`.** Fixture projects use `<CURSOR: expected_name>` directives and are scored by
  mean reciprocal rank (`ty_completion_eval/README.md:85-112`).
- **Assessment (Recommendation):** as with mdtest in the earlier note, copy the *ideas*: one cursor per
  assertion, plain-text and Markdown snapshotted together, hard-break normalization. Do not copy the
  harness. `<CURSOR>` makes a file invalid Python, and our feature folders must stay installable
  extensions (earlier note §3). The in-memory `TestDb` would also need the multi-MB stubs loaded.

### 2.5 Pyright, Pylance and basedpyright, and typeshed (brief)

- **pyright** reads the stub docstring first. If the declaration is in a `.pyi` and has no docstring, it
  uses `SourceMapper` to find the implementation in the `.py` file. This applies to functions, variables
  and classes, and classes also inherit the docstring of the nearest non-builtin base
  (https://github.com/microsoft/pyright/blob/main/packages/pyright-internal/src/analyzer/typeDocStringUtils.ts).
  Its fourslash tests mark positions with `/*marker*/` and assert Markdown with `helper.verifyHover`
  (https://github.com/microsoft/pyright/blob/main/packages/pyright-internal/src/tests/fourslash/hover.docstring.overloads.fourslash.ts).
- **basedpyright** bakes docstrings of compiled builtin modules into its bundled typeshed stubs with
  `docify`, because C modules cannot be inspected statically. It suggests
  `python -m docify path/to/stubs --in-place` for third-party stubs
  (https://docs.basedpyright.com/latest/benefits-over-pyright/pylance-features/).
- **typeshed** says "Typeshed stubs should not include duplicated docstrings from the source code"
  (https://github.com/python/typeshed/blob/main/CONTRIBUTING.md). The typing guide says stub docstrings
  "do not affect type checking results" but "can improve certain IDE functionality, such as hover info"
  (https://typing.python.org/en/latest/guides/writing_stubs.html, section Docstrings).
- **Consequence for bpy (my inference):** typeshed's "no docstrings" rule assumes there is a `.py` source to
  fall back to. `bpy` has none, so the docstrings must be in the stubs. This is the same situation
  basedpyright and ty solve for the C stdlib with docify and docstring-adder.

---

## 3. What the two stub generators produce today

### 3.1 Sources of prose

| Prose | Origin | In RST docs | fake-bpy-module | Blender `sphinx_stub_gen.py` |
| --- | --- | --- | --- | --- |
| Class description | RNA struct `description` (`_rna_info.py:143`) | yes | class docstring | none |
| Property description + type info (range, default, readonly) | RNA prop `description` + `get_type_description` (`_rna_info.py:308, 425-447`) | yes | attribute docstring, or `@property` body (`writers.py:486-555`) | none |
| Property UI name (`bl_rna...name`) | RNA prop `name` (`_rna_info.py:307`) | no, except operator args ("Size, ...") | only via the operator RST | none |
| Function / parameter / return description | RNA func and param `description` (`_rna_info.py:644`) | yes | docstring with `:param x:` / `:return:`, without `:type:` (`writers.py:338-375`) | none |
| Operator description and args | `InfoOperatorRNA` (`_rna_info.py:674-695`) | yes | `__new__` docstring of a class per operator | none |
| Enum item name + description | RNA `enum_items` (`_rna_info.py:357`) | yes | `# Name.Description` **comment** after each literal (`writers.py:587-607`) | none |
| Deprecation | RNA `is_deprecated`, `deprecated_note`, version, removal version (`_rna_info.py:300, 334-341`; `RNA_define.hh:514-521`) | `.. deprecated:: V removal planned in version R` + note (`sphinx_doc_gen.py:2290, 2303-2316`) | the directive text is prepended or concatenated into the description (`writers.py:332-333, 490-492`; `analyzer/directives.py:388-396`) | none |
| Context members (`bpy.context.active_object`) | C context member lists | `:type:` only, **no prose** (`.cache/bpy-rst/main/sphinx-in/bpy.types.Context.rst:456-458`) | `"""(readonly)"""` | none |

`blender/doc/python_api/sphinx_stub_gen.py:65-120`: `MethodInfo`, `AttrInfo`, `ClassInfo`, `FunctionInfo`
and `DataInfo` carry names, parameters and types only. *Verified locally:* 0 docstrings in
`.cache/bpy-stubs-builtin/main`.

### 3.2 Coverage numbers (*verified locally*, fake-bpy-module 5.2, `ast` scan)

- 21 362 functions, of which 14 961 have `:param` in the docstring.
- 23 708 annotated class attributes, of which 9 975 have an attribute docstring. Readonly RNA properties
  are emitted as `@property` with a body docstring instead (`writers.py:510-530`), so they are not
  counted here.
- Bulk hover over every attribute and method of 8 classes, 671 hovers:

  | Class | Hovers without a docstring section |
  | --- | --- |
  | `Context` | 97 / 125, matching the RST gap above |
  | `Mesh` | 3 / 81 |
  | `Object`, `Operator`, `Panel`, `UILayout` | 1 each |
  | `Scene`, `Material` | 0 |

### 3.3 Concrete defects that only show in the editor (*verified locally*)

1. **Parameter docs lost through mixed indentation.**
   - **The shape of the docstrings.** fake-bpy-module writes the summary at the method's body indent and
     `:param` lines 8 columns deeper. Multi-line return descriptions and enum expansions are at the body
     indent, as in `Object.ray_cast` (`.cache/bpy-stubs/5.2/bpy-stubs/types/__init__.pyi`).
   - **What trimming does.** PEP 257 trimming strips only the *common* indent, so the `:param` lines keep
     8 spaces. They are no longer a top-level field list (`rst.rs:21-32`).
   - **What the editor shows.** Hover shows them as `&nbsp;&nbsp;…:param origin: …`. Keyword hover on
     `distance=` has no documentation. Signature help has no per-parameter documentation.
   - **Control.** The same text with uniform indentation (`Object.select_set`, or a hand-written control
     stub) gives `## Parameters` and keyword documentation.
   - **Scale.** 934 of 14 961 `:param` docstrings are affected. They include all `bpy.props.*Property`
     functions and operators with enum parameters (`bpy.ops.mesh.primitive_cube_add`).
2. **Enum item descriptions are invisible.**
   - **Where they are.** `"FINISHED",  # Finished.The operator exited…` is a comment in
     `bpy-stubs/stub_internal/rna_enums/__init__.pyi`.
   - **What hover and completion see.** Hover on the literal `"FINISHED"` returns `null` (`hover.rs:59-63`).
     The property docstring only says `(default 'EMPTY', readonly)`.
   - **Formatting.** Name and description are glued together without a space (`Finished.The`).
3. **Deprecation is unreadable.**
   - **The rendered text.** `Brush.falloff_angle` in `main` renders as `…(in [0, 1.5708], default
     0.0)Automasking 'View Normal' should be used instead5.3 removal planned in version 6.0`. The words
     "Deprecated" and "since" are gone.
   - **What is missing.** No `@deprecated` decorator is emitted anywhere in either stub set, so there is
     no diagnostic and no strike-through.
4. **Apostrophes stripped.** `process_description_str` deletes every `'` from function, class and
   constant docstrings (`writers.py:50-51`), giving "Contexts depsgraph" and "isnt". Attribute docstrings
   are written raw (`writers.py:520-528, 536-546`).
5. **ty side:**
   - completion documentation for attributes comes from the type (§2.3);
   - signature help is plain text only (§2.3);
   - user-defined `count: IntProperty(description="…")` hovers as `Unknown`, so the user's own `description=` never shows.

---

## 4. Recommended test layout and marker syntax (Recommendation)

### 4.1 Layout: extend the earlier tree, don't fork it

```text
tests/typecheck/
├── features/<feature>/
│   ├── __init__.py                  # unchanged: idiomatic addon
│   ├── check_<feature>.py           # types: assert_type / ty: ignore (earlier note)
│   └── ide_<feature>.py             # editor: caret markers (this note); never imported by __init__
├── ide/                             # IDE-only features with no type assertions
│   ├── hover_rna_props/ide_hover_rna_props.py
│   ├── signature_ops/ide_signature_ops.py
│   ├── completion_docs/ide_completion_docs.py
│   ├── enum_docs/ide_enum_docs.py
│   └── deprecation/ide_deprecation.py
└── expected/
    ├── fake-bpy-module/5.2.txt      # type results (earlier note)
    ├── fake-bpy-module/5.2.ide.md   # IDE golden file (this note)
    ├── builtin/main.txt
    └── builtin/main.ide.md
.cache/typecheck-results/<version>/<generator>/ide.json     # raw LSP responses, for debugging
```

### 4.2 Marker syntax

A comment line *below* the target puts a caret at the column to query. The word after the caret names the
request, and an optional quoted string gives the expectation. The file stays valid, installable Python,
and markers survive formatting because they are comments.

```python
def _(obj: Object) -> None:
    obj.location
    #   ^hover
    obj.location
    #   ^hover-contains "Location of the object"
    obj.ray_cast((0, 0, 0), (0, 0, 1), distance=1.0)
    #                                  ^hover-contains "Maximum distance"
    obj.ray_cast((0, 0, 0), (0, 0, 1))
    #             ^signature
    obj.locat
    #        ^completion location
    obj.type == "MESH"
    #            ^hover-contains "Mesh"           # today: null (xfail via golden file)
```

| Marker | Request | Pass condition |
| --- | --- | --- |
| `^hover` | `textDocument/hover` | normalized Markdown recorded in the golden file (snapshot only) |
| `^hover-contains "text"` | hover | the normalized *plain text* contains `text` |
| `^hover-none` | hover | result is `null` |
| `^signature` | `textDocument/signatureHelp` | label, active parameter and every parameter's documentation recorded |
| `^signature-param "text"` | signature help | the active parameter's documentation contains `text` |
| `^completion a b c` | `textDocument/completion` | items `a b c` exist; their `detail` and `documentation` are recorded |
| `^deprecated` | `textDocument/diagnostic` (or `ty check`) | a `deprecated` diagnostic covers the caret column |

Why this shape:

- **The caret line.** It mirrors the visual style of ty's diagnostic snapshots (`hover.rs:554-560`) and of
  mdtest's assertions-on-adjacent-lines idea (earlier note §2.1).
- **`-contains` assertions do not depend on rendering.** They assert the RNA *content*, while `^hover`
  snapshots catch rendering changes. The two generators share one file. A missing docstring with the
  built-in generator is a recorded known state in `builtin/main.ide.md`, not a failure, which follows the
  same "fail on change" rule as the earlier note's expectation files (§4 there).
- **Positions are 0-based LSP line and character.** Test files must be ASCII so that UTF-16 code units
  equal columns. *Assumption*: the client does not negotiate `positionEncoding`.

### 4.3 Golden-file format

Markdown, one section per marker, sorted by file and line, with plain text and Markdown both kept, as in
ty's own hover snapshots (`hover.rs:7444-7451`).

````markdown
## features/props_annotations/ide_props_annotations.py:12 ^hover `obj.location`

```python
Vector
```
---
Location of the object (array of 3 items, in [-inf, inf], default (0.0, 0.0, 0.0))

## features/props_annotations/ide_props_annotations.py:16 ^signature `obj.ray_cast(`

label: (origin: Sequence[float] | Vector | None, direction: …, *, distance: float | None = ..., depsgraph: Depsgraph | None = None) -> tuple[bool, Vector, Vector, int]
active: 0
params:
- origin: <no documentation>
- direction: <no documentation>
documentation: |
  Cast a ray onto evaluated geometry, …
````

Normalization before writing and comparing:

1. `"  \n"` → `"<HB>\n"`, as ty does in `hover.rs:519`.
2. Decode `&nbsp;` to a visible `·`, so indentation bugs stay visible in the diff.
3. Strip the trailing whitespace of each line.
4. Replace the stub search path with `<stubs>`.
5. Drop `range`, but record a range mismatch with the expected token as a separate line.

---

## 5. Harness sketch (Recommendation)

### 5.1 Client choice

| Option | Notes |
| --- | --- |
| **Hand-written stdio client** (what the probes used) | About 100 lines. It covers `Content-Length` framing, `initialize`/`initialized`, `didOpen`, requests, a null reply to server→client requests, and `shutdown`/`exit`. No dependencies, so it fits the `uv run` PEP 723 scripts in `scripts/`. |
| `pygls` `BaseLanguageClient` (`pygls.lsp.client`) | Typed `lsprotocol` params, `text_document_hover_async` (https://pygls.readthedocs.io/en/latest/pygls/api-reference/clients.html). Worth using if the harness grows. |
| `multilspy` | It bundles specific servers and lists jedi-language-server for Python, not ty or pyright (https://github.com/microsoft/multilspy). It would need a custom server config; no gain over the two options above. |

I recommend the hand-written client first. The protocol surface is four requests.

### 5.2 Sketch

```python
# scripts/check_ide.py  (uv run, PEP 723; sibling of check_features.py from the earlier note)
MARK = re.compile(r'^\s*#\s*(?P<pad>.*?)\^(?P<kind>[a-z-]+)(?:\s+(?P<arg>.*))?$')

def run(generator, stubs, py_version, files):
    root = make_tmp_project(stubs, py_version)          # ty.toml: [environment] extra-paths, python-version
    with LspClient([ty, "server"], cwd=root) as c:      # capabilities: markdown first for hover + completion
        for f in files:
            text = f.read_text()
            c.did_open(f, text)
            for line_no, line in enumerate(text.splitlines()):
                if (m := MARK.match(line)) is None:
                    continue
                pos = {"line": line_no - 1, "character": line.index("^")}
                yield f, line_no, m["kind"], m["arg"], c.query(m["kind"], f, pos)

def main():
    for generator, stubs in resolve_stubs(...):           # reuse generate_stubs.resolve_generators
        results = list(run(generator, stubs, ...))
        write(".cache/typecheck-results/<v>/<g>/ide.json", results)
        golden = render_golden(results)                   # §4.3 normalization
        failures = check_contains(results)                # ^hover-contains, ^signature-param, ^hover-none
        diff_against("tests/typecheck/expected/<g>/<v>.ide.md", golden, update=args.update)
```

Notes from the probes:

- **Configuration.** `extra-paths` and `python-version` can go in a `ty.toml` in the workspace root.
  The `configuration` editor setting is an alternative (`ty-blender/docs/reference/editor-settings.md:6-15`).
- **Markdown must be requested.** Pass Markdown as the first format in `hover.contentFormat` and
  `completionItem.documentationFormat`. Otherwise ty answers in plain text (§2.3).
- **No wait needed.** `initialize` returns in about 30 ms. The first request then pays for loading the stubs.
  There was no need to wait for workspace diagnostics before hover.
- **Mise task:** `check:ide <version> [--generator] [--update]`, shaped like `check:features`.

### 5.3 Cost and flakiness

- **Cost.** The probes measured 0.28 s for 12 queries, and 0.41 s for 671 hovers on the 5.2 stubs
  (*verified locally*), so per-query cost is negligible next to stub generation. One server per
  generator and version is enough.
- **Determinism.** Two consecutive 671-hover runs were identical (*verified locally*). Completion results
  are ranked, and the response sets `isIncomplete: true` (`requests/completion.rs:159-164`). Assert on the
  selected labels only, never on order or the full list, and never on `sortText`.
- **Fragile parts.**
  - Golden files change on every ty rendering tweak, such as the multiline signature format or Markdown
    escaping, and on every generator change. That is intended, but it means review noise after each
    `ty:build` bump.
  - Keep `-contains` assertions as the stable layer and the full snapshots as review aids, the same split as
    `assert_type` vs `reveal_type` in the earlier note.
- **Not flaky, but environment-sensitive.** The `ty.toml` `python-version` must match Blender's. A file
  inside a directory with a `pyproject.toml` picks up its `requires-python`
  (`ty-blender/ruff/AGENTS.md`, section "Ad hoc reproductions"). Generate the temp project outside the repo.

---

## 6. Generated coverage (Recommendation)

All of this reuses the RNA dump pipeline from the earlier note (§5.1 there). `prop_flags`
(`scripts/blender/dump_rna_flags.py:207-228`) already records `is_deprecated`. It would also need to record
`name`, `description`, `deprecated_note` and versions, and the `(identifier, name, description)` of
`enum_items`, all available on `InfoPropertyRNA` (`_rna_info.py:300-357`).

1. **Property hover contains its RNA description (highest value per cost).** For each struct and property,
   emit `x.<prop>` + `#   ^hover-contains "<description>"` into
   `.cache/typecheck-generated/<v>/ide_<Struct>.py`. Normalize by collapsing whitespace and comparing
   without `'`, because of `process_description_str`. Report the hit rate per generator. Today that is 0%
   for builtin, high for fake-bpy-module, and low for `Context`.
2. **Function parameter docs are reachable.** For each RNA function parameter with a description, emit a
   call with that keyword and `^hover-contains` on it. This directly measures the 934-function
   indentation defect (§3.3.1), and the same text drives `^signature-param`.
3. **Operator docs.** The same as 2, for `bpy.ops.<mod>.<op>(<kw>=…)` from `InfoOperatorRNA`.
4. **Deprecation.** For each `is_deprecated` property, assert either a `deprecated` diagnostic (needs
   `@deprecated` on a `@property` in the stubs) or at minimum `^hover-contains "Deprecated"`. Today both
   fail for both generators.
5. **Enum items.** For each enum-typed property, assert that the item *names* or *descriptions* appear
   somewhere the user can see them. The cheapest options are a list in the property docstring or completion
   `detail` on string-literal completions. Today they appear nowhere (§3.3.2). This is a design question
   more than a test (see §8).
6. **Completion docs for attributes.** `x.<prop prefix>` + `^completion <prop>`, asserting that
   `documentation` contains the RNA description. This currently fails because of ty
   (`completion.rs:450-462`), independent of the stubs. One test per class is enough to track it.
7. **Differential snapshot.** Dump every `^hover` for both generators and diff them. This shows where one
   generator has prose and the other doesn't, and where the type rendering differs, for example
   `None | Scene` vs `Scene | None` in the probes.

### Recommended order of investment

1. **§4–5:** `check:ide` with the hand-written client, `^hover`, `^hover-contains` and `^signature`
   markers in 3–5 hand-written `ide_*.py` files, seeded from the defects in §3.3. Add golden files per
   generator. That is about a day of work. The client is already prototyped.
2. **§6.1:** RNA description coverage of property hovers. It reuses the dump, and the single number per
   generator is useful immediately.
3. **§6.2–6.3:** parameter and operator documentation. It quantifies the fake-bpy-module indentation bug
   and gives a regression test for the fix.
4. **§6.4:** deprecation, once a stub-side representation is decided (§8).
5. **§6.7:** a full differential snapshot for review, not pass/fail.
6. **§6.5–6.6:** enum items and completion docs. Both are blocked on design or ty changes, so track them
   with one or two hand-written markers until then.

---

## 7. Fix candidates the tests would drive (my suggestions, not researched in depth)

- **fake-bpy-module** (`generator/writers.py`):
  - indent continuation lines of `:param` / `:return:` to the field's indent, or dedent the field list;
  - write enum descriptions into the owning property's docstring, or use a `#:` Sphinx-style comment
    (not read by ty either, so a docstring is better);
  - emit `.. deprecated:: V` on its own line plus the note, and/or `@typing_extensions.deprecated(note)`;
  - stop deleting apostrophes.
- **Blender `sphinx_stub_gen.py`:** carry the paragraph text of each RST directive into `AttrInfo` and the
  other info classes and emit it as a docstring. Alternatively, follow ty and basedpyright and run a
  docstring-adder / docify-style pass inside Blender, reading `bl_rna` descriptions at runtime.
- **ty fork:**
  - use the attribute's own definition docstring for member completions;
  - offer Markdown in signature help;
  - set `CompletionItemTag.Deprecated`;
  - accept `.. deprecated:: V free text`;
  - possibly show `description=` of `bpy.props.*Property(...)` annotations on hover.

---

## 8. Open questions

- **Where should enum item documentation live** so an editor can show it? The options are the property
  docstring, a docstring on each enum alias, or hover on string literals in ty, which returns nothing today
  (`hover.rs:59-63`). Each implies a different assertion.
- **How should deprecation be represented in stubs?** `@deprecated` on a `@property` getter gives
  diagnostics and strike-through. A docstring directive only gives text. Should a removed-in-the-future
  property be flagged at all with `blender_version_min` below the deprecation version?
- **Should the builtin generator get docstrings at all?** Upstream it is described as generating stubs
  "for use with mypy" (`sphinx_stub_gen.py:7-9`). If not, the builtin golden file is just a type-only
  baseline. Is that useful, or should IDE tests run only against fake-bpy-module?
- **Plain text vs Markdown as the asserted form.** I propose `-contains` on plain text and snapshots in
  Markdown. Is plain text stable enough across ty versions? It is PEP 257 trimming only (`docstring.rs:29-35`).
- **Context members.** The RST has no prose for `bpy.context.*` (§3.1). Is that a Blender docs gap worth
  fixing upstream (`sphinx_doc_gen.py` context section), or out of scope?
- **pyright and basedpyright comparison.** Running the same markers against `basedpyright-langserver
  --stdio` would separate stub problems from ty problems (for example the completion-doc issue). Is that
  worth a second server in CI?
- **Position encoding.** Not tested with non-ASCII test files. Keep the ASCII-only rule, or negotiate
  `positionEncoding: utf-8`?
