# Exceptions: what Blender's API raises, and what an add-on lets escape

Research note, 2026-11-20.

**Question.** The tooling here analyses a lot about NULL and `None`: which RNA functions can return `None`
(`prototypes/source_stubs/libclang/returns.py`, [source-stub-generators.md](source-stub-generators.md) section 5.1),
and never-null parameters. It does nothing systematic about exceptions. Two questions follow:

1. How could we document which exceptions each Blender Python API call can raise, in Blender's API documentation
   and, if possible, in the `.pyi` stubs?
2. How could we check exception propagation inside an add-on? That is, which exceptions an add-on's code can let
   escape from an operator's `execute`, a draw function or a handler.

**Method.**
- Read the Blender 5.2 source (`.cache/blender-src/5.2-src`, `038a2fc3c26`: `v5.2.0` plus the makesrna dump patch),
  the fork's generators (`blender/`), ty-blender (`ty-blender/ruff-blender` at `3872f740fc`, based on ruff 0.17.5 /
  ty 0.0.103), the feature tests and the prototypes.
- Two counting scripts in the session scratchpad (`exceptions-research/`), with no build:
  - `count_pyerr.py` counts the `PyErr_*` sites under `source/blender/python`.
  - `reports_scan.py` matches the RNA functions in `.cache/source-stubs/5.2/makesrna/facts.json` to their C bodies
    and looks for error reports.
- Ran stock ruff 0.17.5 (`uvx`, `--preview`) and pydoclint 0.12.0 on a 47-line scratch add-on.
- Web sources: PEPs, the typing spec, Sphinx, numpydoc, the Google style guide, pyright, CodeQL, deal, pylint and
  pytype, read as raw files from GitHub or as PyPI metadata. discuss.python.org did not resolve from this session, so
  the typing-forum discussion is cited from search-result snippets and marked as such.
- No mise task, cargo, ty or Blender was run, because another session held the machine-wide lock. Claims are
  marked **verified** (source read or experiment) or **inferred**. Section 10 collects them.

## 1. Answer

1. **Today, exceptions are known only as prose and as hand-written checks.**
   - The stubs carry no raise facts. Blender's own stub generator writes no docstrings at all. fake-bpy-module drops
     the `:raises` field.
   - Blender's rst has 10 `:raises` fields in 1,957 files.
   - Several ty-blender rules *prevent* a specific exception (`blender-duplicate-registration` → `ValueError`,
     `blender-invalid-idname` → `RuntimeError`, `blender-imprecise-enum-value` → `TypeError`, ...). None tracks
     whether an exception escapes.
2. **The exceptions fall into three kinds, and only the first is worth recording per function.**
   - **Per-function facts, readable from the C source** (section 3.6):
     - An RNA function raises `RuntimeError` only through an error report. That needs a `ReportList`, which only
       the 366 of 3,014 RNA functions flagged `FUNC_USE_REPORTS` get. A regex scan finds a direct
       `BKE_report(reports, RPT_ERROR...)` in 257 of them.
     - A C-API method (`mathutils`, `bmesh`, `gpu`, ...) raises what its body sets with `PyErr_*`. There are 1,069
       such sites under `source/blender/python` (a lower bound).
   - **Generic to every call:**
     - `TypeError` / `ValueError` from argument conversion. The stub types already express these, and ty already
       reports them.
     - `ReferenceError` on data invalidated by `remove()`.
     - `AttributeError` when writing ID data in a read-only callback.
     - `RuntimeError` when the Python context is missing.

     These belong in rules, not in per-function facts.
   - **Generic to one family:**
     - Every `bpy.ops` call may raise `RuntimeError`: on a failed poll, an operator error report, or a write
       in a read-only state.
     - Every `bpy_prop_collection[...]` may raise `KeyError` or `IndexError`.
3. **What "unhandled" means depends on the caller** (section 5, read from source). Blender never crashes on an
   escaping exception. It prints the traceback and then:
   - for an operator `execute`/`invoke`/`modal`: the operator keeps the result parameter's *default*,
     `{'FINISHED'}` (`rna_wm_api.cc:1271`), so an undo step is pushed after a half-done edit;
   - for a `poll`: the poll fails;
   - for a draw: the panel is left half drawn;
   - for a timer: the timer is silently unregistered;
   - for a handler, an update callback or a msgbus callback: Blender carries on;
   - for `register()`: the add-on fails to enable, and the classes registered so far stay registered.
4. **Recommendation:**
   1. **Extract raise facts statically**, by extending the libclang `returns.py` walk from "NULL after a report"
      to "any error report or `PyErr_*` on some path". Record the exception type, the message and the source
      location as evidence. makesrna's JSON dump already carries `use_reports`.
   2. **Render the facts as Sphinx `:raises X: <message>` fields.**
      - Upstream: in `sphinx_doc_gen.py`, once a function flag is exposed (`Function.use_reports` is not exposed
        today).
      - Here: in our generated docstrings and stubs.

      For ty, ship them machine-readably next to the stubs. Section 9.3 compares the formats. A stub-only
      decorator is the best fit for ty; a side-car JSON is the best fit for the generator.
   3. **In ty-blender, start with rules that need no propagation analysis and have few false positives.** These
      are `bpy.ops` or ID writes in a read-only callback (always raises), use after `remove()`, and an
      unprotected call in a timer.
   4. **Add an opt-in "escaping exception" rule** for `execute`, handlers and timers last. It would use the
      per-function facts and the `except` clauses' types. Generic exceptions are ignored, as CodeQL ignores
      typing errors.

## 2. What the repo does with exceptions today

**Verified** by grep over `scripts/`, `tests/`, `prototypes/`, `docs/`, `fake-bpy-module/src`, the fork's
`doc/python_api/` and ty-blender's Blender code.

- **Stubs and docs.**
  - Blender's builtin stub generator emits no docstrings. For example, `Matrix.adjugated` in
    `.cache/bpy-stubs-builtin/5.2/mathutils/__init__.pyi:108` is a bare signature, and
    [hover-docstring-testing.md](hover-docstring-testing.md) section 1.2 counts 0 triple-quoted strings in 143
    files.
  - fake-bpy-module keeps docstrings but not `:raises`. Its directive parser keeps only the `type`, `option` and
    `mod-option` fields of data, and the `arg`, `param`, `type`, `return`, `rtype` and `option` fields of
    functions (`fake-bpy-module/src/fake_bpy_module/analyzer/directives.py:506-519`, `531-535`). The rst's
    `:raises ValueError: if the matrix cannot be adjugated.` therefore becomes
    `.cache/bpy-stubs/5.2/mathutils-stubs/__init__.pyi:654-657` without it.
  - The only `:raises` in the generated stubs come from Python modules' own docstrings, such as
    `_bpy_internal/filesystem/locking.py`.
  - The source-reading prototypes record no exception facts, apart from the `raises` verdict for pointer returns.
- **libclang `returns.py`.** It records one exception fact. The `raises` verdict means "NULL only after an error
  report" (`prototypes/source_stubs/libclang/returns.py:12-13`, `43-44`, `465`). 41 pointer-returning functions
  get it (`.cache/source-stubs/5.2/libclang/returns.md`), and the stub keeps them non-optional. It answers "can
  this return `None`?", not "can this raise?":
  - functions without a pointer return are not walked;
  - a report on a path that returns non-NULL is not recorded.
- **Probes.** The probes record exceptions as outcomes but keep no facts:
  - `scripts/blender/probe_never_none.py:38-42` records `raises <Error>: <message>`;
  - `check:load` accepts `expect = "raises"` (`scripts/check_load.py:73-74`, `tests/typecheck/README.md:170`);
  - 11 probes in 8 `_expected/runtime.toml` files expect a raise, for example
    `tests/typecheck/features/api_types/api_never_none/_expected/runtime.toml:28-29`, "node_groups.new() raises
    for an unknown tree type instead of returning None".
- **ty-blender.**
  - Of its 39 Blender lint rules (`crates/ty_python_semantic/src/types/dedicated/blender/lints.rs`), 17
    lint docs justify the rule by the exception Blender raises (`resources/lint_docs/blender-*.md`). For example:
    - `blender-duplicate-registration`: `ValueError`;
    - `blender-register-order`: `ValueError` or `RuntimeError`;
    - `blender-unregister-mismatch`: `RuntimeError`;
    - `blender-invalid-operator-property`: `TypeError`;
    - `blender-assumed-preferences`: `AttributeError`.
  - Two walks model `raise` and `try` for their own purposes, and treat any exception alike:
    - `poll_checks.rs:953-958` treats `raise` as leaving the block. `poll_checks.rs:1009-1030` treats an
      `except` as "only what was known before the `try` holds" (a poll that raises is a failed poll).
    - The registration walk assumes a `try` body "may register and then raise" (`walk.rs:722`).
  - No rule names an exception type.

## 3. Where Blender's exceptions come from (5.2)

All file:line references are under `.cache/blender-src/5.2-src/source/blender/` unless they say otherwise.
**Verified** by reading.

### 3.1 Calling an RNA function (`pyrna_func_call`, `python/intern/bpy_rna.cc`)

| Exception | When | Where |
|---|---|---|
| `TypeError` | more positional arguments than parameters; an optional parameter given by position ("must be keywords"); a required one missing; an unknown keyword | `bpy_rna.cc:7012`, `7039-7046`, `7069`, `7174` |
| `TypeError`, `ValueError`, `AttributeError` | argument conversion fails. `pyrna_py_to_prop` re-raises with the parameter prefix (`7093-7099`). Its sites: 19 `TypeError`, 1 `ValueError`, 1 `AttributeError`, 1 `RuntimeError` (`1656-2250`). Examples: `None` for a `PROP_NEVER_NULL` pointer (`2015-2016`), an enum string not among the items (`1361`, `1370`), a set expected for an enum flag (`1392`) | `bpy_rna.cc:1656-2250` |
| `RuntimeError` | the C function stored a report of level `RPT_ERROR` or above. `BPy_reports_to_error` joins every such report into the message (`python/intern/bpy_capi_utils.cc:24-40`) | `bpy_rna.cc:7190-7197` |
| `RuntimeError` | an internal NULL pointer or function ("this is a bug") | `bpy_rna.cc:6969-6982` |

`RNA_function_call` passes a `ReportList` only to functions defined with `FUNC_USE_REPORTS` (`makesrna/RNA_types.hh:937`,
`makesrna/intern/makesrna.cc:2317`, `2596`, `3143`). An RNA function without that flag therefore cannot raise
`RuntimeError` through a report. That makes the flag a cheap, sound over-approximation of "may raise
`RuntimeError`".

The report levels are `RPT_ERROR`, `RPT_ERROR_INVALID_INPUT`, `RPT_ERROR_INVALID_CONTEXT` and
`RPT_ERROR_OUT_OF_MEMORY` (`blenkernel/BKE_report.hh:41-44`). `RPT_WARNING` (`:40`) never raises. Counted over
`makesrna/intern/*.cc` (calls written `BKE_report[f](reports, RPT_...)`): 236 `RPT_ERROR`, 5
`RPT_ERROR_INVALID_INPUT`, 9 `RPT_WARNING`, 2 `RPT_DEBUG`.

From makesrna's dump (`.cache/source-stubs/5.2/makesrna/facts.json`): 366 of 3,014 RNA functions have
`use_reports`, and none of them is a registerable callback. `reports_scan.py` (a regex, so an estimate) matched
each one's C body:

| C body | Functions | Example |
|---|---|---|
| reports `RPT_ERROR` directly | 257 | `ID.update_tag` (`makesrna/intern/rna_ID.cc:1083`) |
| passes `reports` to a callee | 57 | `Library.reload` (`rna_ID.cc:1645`) |
| body not found in `makesrna/intern` (defined in editors or blenkernel) | 51 | `MeshVertices.add`, `FCurve.update_autoflags` |
| `reports` unused | 1 | `NodeTreeInterface.move_to_parent` (`rna_node_tree_interface.cc:902`) |

The report messages document the condition. For example, `BlendDataObjects.remove` reports "Cannot remove volume
light probes while light probe baking is running" (`makesrna/intern/rna_main_api.cc:140-143`), which is exactly
what a `:raises RuntimeError:` line should say.

### 3.2 Attribute access, collections and stale data

- **`ReferenceError` for removed data.**
  - Every struct method and attribute access starts with `PYRNA_STRUCT_CHECK_OBJ` (`python/intern/bpy_rna.hh:81-84`;
    the `bpy_struct` methods at `bpy_rna.cc:3674-4745`).
  - It raises "StructRNA of type X has been removed" when the pointer's type was cleared
    (`bpy_rna.cc:183-197`). `PointerRNA::invalidate()` exists for this (`makesrna/RNA_types.hh:105-115`), and
    `remove()` functions call it on their argument, e.g. `rna_main_api.cc:150`, `161`; there are 80 calls in
    `makesrna/intern/*.cc`.
  - The full weakref invalidation of every Python object of a freed ID (`BPY_id_release`, `bpy_rna.cc:428-446`)
    only exists with `WITH_PYTHON_SAFETY` (`python/intern/bpy_rna.hh:20-35`), which is off by default
    (`CMakeLists.txt:220-225`).
  - In a release build, only the object passed to `remove()` raises. Anything else that pointed into the freed
    data may crash. The manual says so: `doc/python_api/rst/info_gotchas_crashes.rst:238-260` ("this is limited
    to scripts accessing the variable which is removed, the next example will still crash").
- **`AttributeError`:**
  - an unknown attribute (`bpy_rna.cc:4926` and the generic lookup);
  - a read-only property (`bpy_rna.cc:5078`, `5091`; a read-only Context member `5120`);
  - a Context member the current editor does not provide (`bpy_rna.cc:4919-4921` falls back to the generic lookup,
    which raises; `CTX_RESULT_NO_DATA` gives `None` instead, `4914-4917`);
  - a NULL context (`4802`).
- **`AttributeError` for writes in read-only callbacks.**
  - `bpy_class_call` disallows writes while it runs a registered callback that lacks `FUNC_ALLOW_WRITE`
    (`bpy_rna.cc:9794-9798`, `9981-9984`).
  - A write to ID data (except window manager, screen and workspace) then raises "Writing to ID classes in this
    context is not allowed" (`bpy_rna.cc:453-480`).
  - Per the makesrna dump, 47 registerable callbacks lack the flag. Among them are `Panel.draw`, `Panel.poll`,
    `Menu.draw`, `UIList.draw_item`, `Operator.poll`, `Operator.draw`, `Operator.description`, `Node.draw_buttons`,
    `Gizmo.draw` and `GizmoGroup.refresh`.
  - 26 have the flag: `Operator.execute`, `invoke`, `modal`, `check` and `cancel`, `Node.init` and `update`,
    `RenderEngine.render`, ...
- **Collections.** `bpy_prop_collection[...]` raises `IndexError` for an integer out of range (`bpy_rna.cc:2456`,
  `2524`) and `KeyError` for a missing name (`bpy_rna.cc:2583`, and the `(name, library)` key forms after it).
- **`mathutils` objects that wrap RNA data** raise:
  - `RuntimeError` "read, user has become invalid" (`python/mathutils/mathutils.cc:563-564`);
  - `TypeError` "is frozen (immutable)" (`mathutils.cc:612`, through the `BaseMath_*_ForWrite` macros,
    `mathutils.hh:157-171`);
  - `ValueError` for a resize of wrapped or frozen data (`mathutils.cc:624`, `628`).

### 3.3 `bpy.ops` (`python/intern/bpy_operator_function.cc`)

Every operator call can raise, before or after running the operator:

| Exception | When | Where |
|---|---|---|
| `RuntimeError` | no context ("Context is None") | `:248-250` |
| `AttributeError` | unknown operator | `:255-259` |
| `RuntimeError` | blend data cannot be modified (drawing or rendering: `pyrna_write_check()`) | `:263-268` |
| `TypeError` | unknown execution context string | `:274-281` |
| `RuntimeError` | the poll fails: "Operator bpy.ops.X.poll() failed, context is incorrect", or the poll's own message | `:287-297` |
| `TypeError` / `ValueError` | keyword arguments that do not convert to operator properties (`pyrna_pydict_to_props`) | `:303-306` |
| `RuntimeError` | the operator reported an error (`BPy_reports_to_error` on its report list) | `:335` |
| `ValueError` | bad positional arguments (string after the bool, more than 2) | `:128`, `:140` |

**Inferred** from `bpy_class_call` (section 5): when the called operator is an add-on's Python operator whose
`execute` raised, the traceback becomes an `RPT_ERROR` report on the operator's report list. The caller then gets
a `RuntimeError` that carries the inner traceback as text, so a Python exception crosses `bpy.ops` as
`RuntimeError`.

The manual documents the poll case: `doc/python_api/rst/info_gotchas_operators.rst:15-26` and `49`, and
`info_quickstart.rst:267-273`.

### 3.4 The C-API modules

`count_pyerr.py` counts direct `PyErr_SetString`, `PyErr_Format`, `PyErr_SetObject` and `PyErr_FormatV` calls with
a literal exception, plus `PyErr_NoMemory` / `PyErr_BadArgument`, under `source/blender/python`. **Verified count,
lower bound**: raises through helpers are not counted. Those include `PyC_Err_Format_Prefix`, the
`mathutils_array_parse` family, `PyArg_ParseTuple*` and the check macros below.

| Directory | Sites | Top exception types |
|---|---|---|
| `intern` (bpy, bpy.props, bpy.ops, bpy.app, ...) | 442 | TypeError 220, ValueError 113, AttributeError 45, RuntimeError 28, KeyError 14, IndexError 8 |
| `mathutils` | 278 | ValueError 102, TypeError 84, RuntimeError 24, MemoryError 22, AttributeError 21, IndexError 12 |
| `bmesh` | 127 | ValueError 52, TypeError 48, AttributeError 6, KeyError 5, IndexError 4, RuntimeError 3 |
| `generic` (idprop, py_capi_utils, ...) | 111 | TypeError 47, ValueError 25, RuntimeError 13, KeyError 6, OverflowError 5 |
| `gpu` | 111 | ValueError 37, TypeError 26, RuntimeError 20, AttributeError 10, BufferError 4 |
| **total** | **1,069** | TypeError 425, ValueError 329, RuntimeError 88, AttributeError 83, IndexError 29, MemoryError 29, KeyError 25, BufferError 11, ReferenceError 9, SystemError 7, ... |

Module-wide check macros add generic exceptions to many methods at once:
- `gpu`: `BPYGPU_IS_INIT_OR_ERROR_OBJ` raises `SystemError` when the GPU is not initialised
  (`python/gpu/gpu_py.cc:58-68`, used 79 times). This matters in background mode.
- `bmesh`: `BPY_BM_CHECK_OBJ` raises `ReferenceError` for a freed BMesh or element (`python/bmesh/bmesh_py_types.hh:239`,
  `bmesh_py_types.cc:5354`, `5363`; used 189 times).

### 3.5 Python-side modules

Explicit `raise` statements, counted with grep (**verified**):

| Module | Explicit raises |
|---|---|
| `scripts/modules/_bpy_types.py` | 5 `ValueError`, 1 `IndexError` (`path_resolve`-style helpers, `:61-85`), 1 `RuntimeError` (`:601`) |
| `bpy/utils/__init__.py` | 6 `raise Exception` |
| `bpy_extras` | 4 `Exception`, 1 `RuntimeError`, 1 `ValueError` |
| `addon_utils.py` | 4 `ValueError`, 1 `RuntimeError`, 1 `ImportError` |

`bpy.utils.register_class` is C (`pyrna_register_class`, `bpy_rna.cc:10361`). In its body: 3 `ValueError`, 2
`RuntimeError`, plus validation in `bpy_class_validate_recursive` (`9537`). Most of these are what ty-blender's
registration rules already predict. These Python functions are readable with `ast` by the shared reader
(`prototypes/source_stubs/common/pysource.py`), the same way pydoclint reads them.

### 3.6 What can be classified per function

| Source | Static per-function fact? | How |
|---|---|---|
| RNA function error report → `RuntimeError` | **yes** | `use_reports` flag (exact upper bound). A path walk to `BKE_report[f]` with a level ≥ `RPT_ERROR`, through callees that get `reports`, using `returns.py`'s lowering and callee following. The message string is the condition. |
| C-API method `PyErr_*` → X | **yes** | `PyMethodDef` / `PyGetSetDef` tables (already read by both source readers) → C function → `PyErr_*` sites and known raising helpers on its paths |
| C-API module-wide checks (`SystemError` in `gpu`, `ReferenceError` in `bmesh`) | yes, but generic per module | the macro use in the body |
| Python-module `raise` | **yes** | `ast` |
| `bpy.ops.X()` → `RuntimeError` | generic to all operators. Per operator: its poll and its exec's error reports. | libclang already knows `ot->poll` / `ot->exec`. The walk is the same as for RNA functions. |
| Argument conversion `TypeError` / `ValueError` | generic | already expressed by the stub types. ty reports a wrong argument type statically. |
| `ReferenceError` on removed data | generic | a dataflow rule in the add-on (use after `remove()`), not a fact |
| `AttributeError` on write in a read-only callback | generic per callback | `FUNC_ALLOW_WRITE` per callback (makesrna dump) |
| `KeyError` / `IndexError` on collection subscripts | generic per family | stub-level on `bpy_prop_collection.__getitem__` |

## 4. Blender's documentation

- **`:raises` fields are rare** (**verified**). There are 10 fields in the 5.2 rst (`.cache/bpy-rst/5.2/sphinx-in`), all
  from C docstrings written by hand:
  - `mathutils/mathutils_Matrix.cc:1868`, `1908`;
  - `python/intern/bpy_utils_units.cc:168`, `256`;
  - `python/intern/bpy_rna.cc:4114`, `4196`, `10352`;
  - `python/intern/bpy_utils_previews.cc:46`, `83`;
  - `python/generic/idprop_py_api.cc:1739`.

  One more, `idprop_py_ui_api.cc:988`, does not reach the rst. Python modules add a few in their own docstrings.
  No RNA function or operator has one.
- **The RNA reference has no slot for exceptions.**
  - `sphinx_doc_gen.py` writes each RNA function as the description, then `write_param` per argument, then the
    return fields (`doc/python_api/sphinx_doc_gen.py:2531-2590`). Operators get a fixed `:return:` / `:rtype:`
    (`:2850-2851`).
  - `_rna_info.InfoFunctionRNA` has no flag beyond `use_self` and the like (`scripts/modules/_rna_info.py:641-653`).
  - The runtime `bpy.types.Function` exposes `is_registered`, `is_registered_optional`, `use_self` and
    `use_self_type`, but not `FUNC_USE_REPORTS` (`makesrna/intern/rna_rna.cc:3516-3570`).
- **The prose guides explain the main generic cases:**
  - `ReferenceError` after `remove()` (`info_gotchas_crashes.rst:238-260`);
  - poll failures as `RuntimeError` (`info_gotchas_operators.rst:15-26`);
  - `bpy.context` writes raising (`info_quickstart.rst:229`).
- **Where a Raises section could be injected:**
  - *Upstream, with the least change:*
    1. expose `Function.use_reports` as one more read-only boolean in `rna_rna.cc`, next to `use_self_type`;
    2. carry it in `_rna_info.InfoFunctionRNA`;
    3. have `sphinx_doc_gen.py` write `:raises RuntimeError: If the operation fails (an error is reported).` after
       the return fields.

    This is a small patch (**inferred** size: under 30 lines), sound, and needs no analysis, but it gives no
    conditions.
  - *Upstream, with conditions:* a hand-written `:raises:` line in the RNA description. RNA descriptions are
    single strings that are also UI tooltips (`RNA_def_function_ui_description`), so prose there is shown in the
    UI. A separate optional "raises" string on `FunctionRNA` would be cleaner, but it is a DNA-free yet
    makesrna-wide change, and less likely to be accepted (**inferred**).
  - *Our side:*
    - the fork's `_rna_info` / stub generators, which already diverge to honour `is_never_none` (`blender/scripts/modules/_rna_info.py:588-595`);
    - or the source-stub renderer (`prototypes/source_stubs/common/render.py`), fed with extracted facts
      including messages.

    This needs no upstream buy-in.

## 5. What Blender does with an exception that escapes add-on code

What "unhandled" means for a check. **Verified by reading**; the operator-result rows are **not yet confirmed by
running** (section 10).

| Entry point | Called by | What happens to the exception | Consequence |
|---|---|---|---|
| `Operator.execute` / `invoke` | `rna_operator_exec_cb` / `_invoke_cb` → `bpy_class_call` (`makesrna/intern/rna_wm.cc:1610-1638`, `1666-1696`) | Turned into an `RPT_ERROR` report on `op->reports` (`bpy_rna.cc:10088-10107`, `BPy_errors_to_report` → `bpy_capi_utils.cc:67-134`), printed (`PyErr_Print`, `:10111`) and logged at ERROR level (`:10115-10118`). Modal handlers are removed (`rna_wm.cc:1631-1634`). | The result parameter keeps its default, `OPERATOR_FINISHED` (`rna_wm_api.cc:1269-1273`, defaults set by `RNA_parameter_list_create`, `makesrna/intern/rna_access.cc:7545-7600`). `wm_operator_exec` then registers the operator and pushes undo (`windowmanager/intern/wm_event_system.cc:1411-1420`). From `bpy.ops`, the caller gets `RuntimeError` (section 3.3). |
| `Operator.modal` | `rna_operator_modal_cb` (`rna_wm.cc:1698-1722`) | Same report and print, with no `has_error` branch. | Ends with the default `FINISHED`, so the modal operator stops (**inferred**). |
| `poll` (`Operator`, `Panel`, `Menu`, ...) | `rna_operator_poll_cb` (`rna_wm.cc:1586-1608`) and the UI equivalents | Printed and reported to the window manager's reports. | `visible` keeps its default `False` (`rna_wm_api.cc:1259`), so the poll fails, on every redraw. |
| `Panel.draw` / `Menu.draw` / `UIList.draw_item` | `makesrna/intern/rna_ui.cc:128-187` → `bpy_class_call` | Printed and reported to `CTX_wm_reports` (the Info editor) (`bpy_rna.cc:10096-10103`). | The layout built so far is shown, and the rest is missing. Repeats on every redraw. |
| A `bpy.app.handlers` callback | `bpy_app_handlers.cc:466-486` | "Error in bpy.app.handlers.X[i]:" plus the traceback on stderr. | The remaining handlers in the list still run. |
| `bpy.app.timers` | `bpy_app_timers.cc:22-27`, `44-55` | Printed. | The callback's return becomes `-1`, so the **timer is unregistered**. |
| A property `update` callback | `python/intern/bpy_props.cc:720-750` | `PyC_Err_PrintWithFunc`. | The value is already set; the update is lost. |
| A property `get` callback | `bpy_props.cc:788-801` (boolean; the other types alike) | Printed. | Returns a fallback (`false`, 0, ...), so the read silently gives a wrong value. |
| `msgbus` notify | `python/intern/bpy_msgbus.cc:158-167` | Printed. | Ignored. |
| `draw_handler_add` callback | `python/intern/bpy_rna_callback.cc:49-67`, `100-116` | `PyErr_Print`. | The callback stays installed and fails each redraw. |
| Driver expression | `python/intern/bpy_driver.cc:292-293`, `507-508` | `PyErr_Print`. | The driver value falls back. |
| `register()` / `unregister()` | `scripts/modules/addon_utils.py:541-553`, `592-599` | "Exception in module register():" plus `handle_error`. The module is removed from `sys.modules`. | The add-on is not enabled. Classes registered before the exception stay registered: no rollback in that code (**inferred** from reading). |

Not a crash anywhere, but three outcomes are worse than a printed traceback, and they are what a check should
target:
1. a half-done edit committed as an undo step (`execute`, `invoke`);
2. a timer that silently stops;
3. a partial registration.

## 6. Exceptions in stubs and the type system

- **Python has no checked exceptions, and the typing standard has no raises annotation** (**verified**). PEP 484:
  "No syntax for listing explicitly raised exceptions is proposed. Currently the only known use case for this
  feature is documentational, in which case the recommendation is to put this information in a docstring" (PEP
  484, *Exceptions*).
- **The only standard spelling is `NoReturn` / `Never`, for a function that never returns normally** (**verified**).
  Checkers treat code after such a call as unreachable (typing spec, *Special types*: `NoReturn`). It cannot say
  "may raise X".
- **Typing-forum proposals.** Threads include "Extend type hints to cover exceptions" (2023), "PEP 484: When will
  we have syntax for Exceptions?" and "Statically tracked exceptions in Python's type system to support EAFP". The
  syntaxes proposed include `@raises(X)` decorators, `Annotated` metadata and a `Raises[T, E]` return form.
  **Unverified**: discuss.python.org did not resolve from this session, and this summary comes from search
  snippets. They report no accepted PEP, and one later reply calls it "not going to happen". No PEP draft was found.
- **Docstring conventions** (**verified**). Three styles carry raises today:
  - Sphinx info fields: `:raises X: when` (aliases `raise`, `except`, `exception`; Sphinx
    `doc/usage/domains/python.rst:671-672`, `702-703`);
  - numpydoc `Raises` (`doc/format.rst:311-325`: "used judiciously, i.e., only for errors that are non-obvious or
    have a large chance of getting raised");
  - Google `Raises:`. The guide adds: "You should not document exceptions that get raised if the API specified in
    the docstring is violated" (styleguide `pyguide.md:2263-2270`).

  That last rule is exactly why generic `TypeError` from wrong argument types should not be in per-function facts.
- **Stubs and docstrings** (**verified**). typeshed's policy is "Typeshed stubs should not include duplicated
  docstrings" (`CONTRIBUTING.md:398-400`). The typing guide leaves it to the stub author: docstrings "can improve
  certain IDE functionality, such as hover info" (`docs/guides/writing_stubs.rst:893-901`). Our stubs are not
  typeshed, so docstrings are acceptable; fake-bpy-module ships them.

## 7. ty and ruff today

**ty (upstream, as forked).**
- The semantic index models `try` as control flow (**verified**):
  - Before every operation that may raise (any call or binary operation, and attribute or subscript accesses
    that can raise), it records an *exception checkpoint* for the enclosing `try` or `with` contexts
    (`crates/ty_python_core/src/builder.rs:2440-2487`, `3699-3702`).
  - The `except` suites start from the merge of those checkpoints (`builder.rs:5124-5240`).
  - Handlers are classified only as "none", "propagating" or "catch-all" (a bare `except:`)
    (`builder/except_handlers.rs:8-36`). The *types* in `except X` are visited as expressions but do not filter
    flow. There is no notion of which exception a call raises.
- `NoReturn`/`Never` calls end a path (`ty_python_core/src/predicate.rs:191`).
- The exception-related rules (`crates/ty/docs/rules.md`) are `invalid-raise` (raising a non-exception) and
  `invalid-exception-caught` (catching a non-exception class).
- ty has no unreachable-`except` rule (pyright has `reportUnusedExcept`) and no raises analysis.

**ruff 0.17.5** (the fork's base; **verified** in `crates/ruff_linter/src/codes.rs:555`, `1076-1085`, `1135`,
`1152-1158`, and by running it):
- `BLE001` (blind `except Exception`), `E722` (bare except), `S110`, `SIM105`, the `TRY*` style rules (`TRY002-004`,
  `200`, `201`, `203`, `300`, `301`, `400`, `401`), `RSE102`;
- `DOC501` / `DOC502`: a raised exception missing from, or extraneous to, the docstring (preview, pedantic;
  `pydoclint/rules/check_docstring.rs:379`).

The scratch experiment (`exp/addon.py`) showed the limits of `DOC501` / `DOC502`:
- They see only explicit `raise` statements in the body. `DOC502` flagged a documented `KeyError` that
  `bpy.data.objects[name]` really raises ("Raised exception is not explicitly raised").
- They parse only Google and NumPy sections (`check_docstring.rs:738-742`). A Sphinx `:raises KeyError:` was
  reported as missing.
- They are not interprocedural. A call to a function that raises `ValueError`, made inside `execute`, gave nothing.

## 8. Existing tools for exception analysis in Python

| Tool | What it does | Maintained | Could use Blender raise facts? | Licence |
|---|---|---|---|---|
| ruff `DOC501/502`, `BLE`, `TRY` | Docstring vs. explicit `raise` in the same function; handler style | yes (0.17.5) | No input for external facts. Blender facts would need a ty-blender rule instead. | MIT |
| [pydoclint](https://github.com/jsh9/pydoclint) | Same check as `DOC5xx`, all three styles incl. Sphinx (`DOC501`, `DOC502`, `DOC503`). Verified: it accepted `:raises KeyError:` with `--style=sphinx`. | yes (0.12.0, 2026-10-28) | No; its own docs say a body without `raise` "doesn't mean that the function doesn't raise anything" (`docs/config_options.md:530-531`) | MIT |
| pylint `docparams` (`W9006 missing-raises-doc`) and exception checker (`E0701` bad except order, `W0718`, ...) | Same as above, plus order of handlers | yes (4.1.4) | No | GPL-2.0-or-later |
| [darglint](https://github.com/terrencepreilly/darglint) | Docstring vs. raises (Google) | no: last release 1.8.1, 2021-10-18 | - | MIT |
| [flake8-raise](https://pypi.org/project/flake8-raise/) | Style of `raise` statements | no: 0.0.5, 2020 | - | MIT |
| [tryceratops](https://pypi.org/project/tryceratops/) | Handler anti-patterns (ported into ruff `TRY`) | low: 2.4.1, 2024-10 | - | MIT |
| [deal](https://github.com/life4/deal) | `@deal.raises(...)` contracts checked at runtime and by its linter (`DEL021`). The linter follows one call level and reads **JSON stubs of raised exceptions** for code it cannot see (`docs/details/stubs.md`; format `{func: {"raises": [...], "has": [...]}}`, `deal/linter/_stub.py:40-53`). Ships stubs for the stdlib. | yes (4.24.6, 2025-11) | **Yes, directly**: a generated `bpy` JSON stub in its format would make `deal lint` see Blender raises. Only for functions an add-on decorates with `@deal.raises`, which add-ons would not do. | MIT |
| [CodeQL Python](https://github.com/github/codeql) | The most complete interprocedural model: `FunctionObject.getARaisedType()`, `viableExceptionalExit`, `scope_raises` (`python/ql/lib/semmle/python/types/Exceptions.qll:240-360`). It **assumes typing errors (`TypeError`, `NameError`, `AttributeError`) occur only if explicitly raised or caught**, and ignores asynchronous exceptions and `MemoryError` (`:1-11`). Queries include "Unreachable except block" and "Empty except". | yes | Yes, by modelling `bpy` calls in QL. But the CLI licence allows analysis only of open-source codebases or for research (`codeql-cli-binaries/LICENSE.md:25-45`). | queries MIT, CLI proprietary |
| [pyright](https://github.com/microsoft/pyright) | `reportUnusedExcept` (an unreachable `except` clause, default error in standard mode) and `reportUnreachable`; hover renders docstrings (`docs/configuration.md:232`, `240`, `403`) | yes | Only through docstrings in hover | MIT |
| [semgrep](https://github.com/semgrep/semgrep) | Pattern rules ("`bpy.ops.$X(...)` inside `execute` not inside `try`") | yes (1.186.0) | Hand-written patterns only; no types or interprocedural flow in the open engine (**inferred**) | LGPL-2.1 |
| Pyre / Pysa | Type checking and taint analysis; Pysa can treat `BaseException` as a taint source or sink (`pysa_basics.md:122`, `183`), and has no raises analysis | yes (0.10.0) | No | MIT |
| pytype | Type inference; no raises analysis. Its README: "The last supported Python version for Pytype will be 3.12" | winding down (2024.10.11) | No | Apache-2.0 |
| [returns](https://pypi.org/project/returns/) | `Result`/`Maybe` types instead of exceptions (`@safe` wraps exceptions into `Result`) | yes (0.30.0) | A different programming style. Blender calls stay exception-based. | BSD-3 |
| [exception-control](https://github.com/Julynx/exception-control) | WIP script that reports uncaught exceptions in one file. It understands the exception hierarchy and docstring-documented raises; its README warns that it misses many exceptions and reports some that never occur. | WIP, single author | It reads docstrings, so `:raises` in stubs would feed it in principle | not checked |
| Academic | MOPSA's Python analyses: Fromherz, Ouadjaout, Miné, value analysis inferring uncaught exceptions ([HAL](https://hal.sorbonne-universite.fr/hal-01782390v1/document)); Monat et al., static type analysis by abstract interpretation tracking raised and caught exceptions, ECOOP 2020 ([LIPIcs](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2020.17)). Java uncaught-exception analyses (set-based, interprocedural) are the classic model. | research | Show that whole-program soundness is costly in Python; not a usable tool here. **Read from abstracts in search results only.** | - |

**Assessment.**
- No maintained tool does interprocedural exception analysis for ordinary Python with external facts, except
  CodeQL (licence-restricted) and deal (contract-driven).
- The docstring linters (ruff `DOC`, pydoclint, pylint) are useful for an add-on's own functions, and need nothing
  from us.
- For Blender-specific propagation, ty-blender is the right host. It already resolves Blender symbols, knows the
  callbacks and their classes, and has the `try` structure.
- deal's JSON stub format is a ready-made precedent for a side-car format, and could be emitted for free from the
  same facts.

## 9. Proposed design

### 9.1 A static extractor of raise facts

**A fact** is one entry per callable or attribute:

```json
{
  "BlendDataObjects.remove": [
    {"exception": "RuntimeError", "kind": "report",
     "message": "Cannot remove volume light probes while light probe baking is running",
     "evidence": "source/blender/makesrna/intern/rna_main_api.cc:140", "via": []},
    {"exception": "RuntimeError", "kind": "report",
     "message": "%s '%s' must have zero users to be removed, found %d (try with do_unlink=True parameter)",
     "evidence": "source/blender/makesrna/intern/rna_main_api.cc:165", "via": []}
  ]
}
```

- `kind` is one of:
  - `report`: an RNA error report, so `RuntimeError`;
  - `pyerr`: a direct `PyErr_*`;
  - `helper`: a known raising helper or macro;
  - `python`: an `ast` `raise`.
- `message` is the format string. `via` is the callee chain.
- Facts go next to the existing ones in the shared model (`prototypes/source_stubs/common/model.py`), so the three
  readers and the renderer share them.

**RNA functions.** Reuse `returns.py`'s inputs: the runtime-half parse, callee following and the path walk. The
walk changes in three ways:
1. Walk **every** RNA function with `use_reports`, not only pointer returns. Functions without the flag cannot
   report (section 3.1), so they get no `report` fact, by construction.
2. Record each `BKE_report[f]` with a level ≥ `RPT_ERROR` that is reachable on some path, with its message. Follow
   callees that receive the `reports` argument. Today the walk only sets `st.reported` (`returns.py:465`).
3. Keep the path conditions it already collects. A report whose condition is decided by an argument (e.g. an
   enum value) can then be printed as "when `type` is ...". This is optional, and a later step.

Unknown callees that receive `reports` give `kind: "report", "message": null` (may raise). That is the safe
direction. The regex scan suggests about 257 functions with direct reports, plus 57 with indirect ones and 51
whose bodies live outside `makesrna`. The libclang walk would replace these estimates.

**C-API methods and properties.**
- Both readers already have the `PyMethodDef` / `PyGetSetDef` tables. For each C function, collect the `PyErr_*`
  sites on its paths, and the uses of a small table of helpers:
  - `PyC_ParseBool`, `mathutils_array_parse`, `PyArg_ParseTuple*`: `TypeError` / `ValueError`, argument kind;
  - `BaseMath_ReadCallback`: `RuntimeError`, stale wrapper;
  - `BPY_BM_CHECK_*`: `ReferenceError`;
  - `BPYGPU_IS_INIT_OR_ERROR_*`: `SystemError`.
- Mark each site *argument validation* when its condition reads only the arguments and parsing results, otherwise
  *state*.
- Only *state* exceptions and documented-worthy argument ones are rendered by default. This follows the Google
  rule in section 6. An example of the second kind is `Matrix.inverted` on a singular matrix, which is a real
  condition, not a type violation.
- The regex reader can do this table-driven part; libclang is needed for paths through helpers.

**Operators.** For `bpy.ops.X`, record the generic `RuntimeError` (poll and errors) for every operator. Add the
exec function's error reports when libclang has the `exec` body, as it has `ot->poll` and `ot->exec` names already.

**Python modules.** The `ast` reader adds `raise` facts for `_bpy_types.py`, `bpy.utils`, `bpy_extras` and
`addon_utils`.

**Cross-check.** The `probe_never_none.py` machinery already calls functions in prepared states and records
`raises <Error>: <message>` (`scripts/blender/probe_never_none.py:38-42`). An exception probe in the same style
would confirm or refute a sample of facts at runtime, as `never-none-probe.md` did for the NULL verdicts.

### 9.2 Getting the facts into docs

1. **Upstream, sound and minimal:**
   - expose `Function.use_reports` in `rna_rna.cc` and `_rna_info`;
   - `sphinx_doc_gen.py` writes `:raises RuntimeError: If an error is reported.`

   This covers 366 functions. Could be proposed together with the `is_never_none` fix.
2. **Upstream, with messages:** the facts are generated outside the build, by libclang. Upstream would not run
   that in `sphinx_doc_gen`. A committed facts file, regenerated by a `tools/` script in the style of
   `tools/check_source/static_check_clang.py`, could feed `sphinx_doc_gen.py`. This is plausible but a bigger ask.
3. **Ours:** render `:raises X: message` into our generated docs and docstring-bearing stubs (the source-stub
   renderer, and the fork's generators if they gain docstrings).

   The render rules:
   - one line per exception type;
   - messages deduplicated;
   - at most a few per type;
   - `RuntimeError` reports summarised as "If ..." from the message.

   Sphinx renders the field (section 6). pyright and ty show it on hover as part of the docstring (ty renders
   fake-bpy docstrings, see [hover-docstring-testing.md](hover-docstring-testing.md) section 1.3).

### 9.3 Getting the facts into stubs: format options

| Format | Example | Machine-readable by ty-blender | Other tools | Conditions and evidence | Cost and risks |
|---|---|---|---|---|---|
| **Docstring field** | `"""...\n:raises RuntimeError: If ..."""` | Only by parsing docstring text. ty parses docstrings in `ty_ide` for hover, not in the semantic crate. | Sphinx, pyright and ty hover, pydoclint, exception-control | Message yes, evidence no | Builtin stubs have no docstrings; fake-bpy drops the field (section 2); text is fragile |
| **Stub-only decorator** | `@_raises.raises(RuntimeError)` from a `bpy/_raises.pyi` declared as `def raises(*e: type[BaseException]) -> Callable[[_F], _F]` | **Yes**: ty resolves the decorator and its arguments as types, and an exception class is checked against `except` clauses with ty's own subclass test | Other checkers see an identity decorator; no effect | Types only (a `reason="..."` keyword could carry the message) | Non-standard. Must be added to every generator, and an identity decorator on `@property` / `@overload` needs care. Version-tied to the stubs, which is right. |
| **`Annotated` return** | `def remove(...) -> Annotated[None, Raises(RuntimeError)]` | Yes, through PEP 593 metadata | Ignored by other checkers (standard) | Same as decorator | Clutters every signature and hover; awkward for properties and overloads; `Annotated[None, ...]` reads oddly |
| **Side-car JSON** (`raises.json` next to the stubs, or deal's format) | section 9.1 | Only with a new input pathway: ty-blender's facts are Rust constants or come from stubs (`crates/ty_blender/src/lib.rs:1-10`) | deal (in its format), our docs renderer | **Full**: messages, evidence, `via` | No stub change. Must map names to stub symbols, and ty must find and track the file. |
| `NoReturn` | `-> NoReturn` | yes | all | - | Only for always-raise. No `bpy` function qualifies; useful only for add-on helpers. |

**Recommendation.**
- Keep the **side-car JSON as the generator's output and source of truth**, with evidence and messages.
- Render it two ways:
  1. **docstring `:raises` fields** for people (docs, hover);
  2. a **stub-only decorator** for ty-blender, carrying only types and an optional `reason`.

The decorator keeps ty-blender reading everything from the stubs, as it does now. It also makes facts
Blender-version-specific for free, and needs no new file discovery in ty. Emitting deal's JSON is a cheap extra.

### 9.4 Checking propagation in ty-blender

**Where an exception escapes to.** These are the entry points of section 5:
- Blender callbacks, which ty-blender already identifies (`crates/ty_blender/src/callbacks.rs`);
- functions appended to `bpy.app.handlers.*`;
- the argument of `bpy.app.timers.register`;
- the `update` / `get` / `set` arguments of property declarations, which the property evaluator already reads;
- `msgbus` notify callbacks;
- draw handlers;
- the add-on's `register` / `unregister`.

**Rules, in order of value per effort:**

| Rule (name tentative) | Reports | Needs | Default level | False-positive risk |
|---|---|---|---|---|
| `blender-write-in-readonly-callback` | An assignment to ID-owned data, or a `bpy.ops` call, inside a callback without `FUNC_ALLOW_WRITE` (`Panel.draw`, `poll`, `UIList.draw_item`, ...). It **always** raises (`AttributeError`, `bpy_rna.cc:453-480`; `RuntimeError`, `bpy_operator_function.cc:263-268`). | The callback's write flag as a Rust table (47 / 26 callbacks, section 3.2); the Blender symbol resolution ty-blender has | warn (error once tested) | Low. Writes to `WindowManager`, screen and workspace data are allowed, and so are operator properties (`self.x` in `Operator.draw` is not ID-owned). The table must encode both exemptions. |
| `blender-use-after-remove` | A read of a name after it was passed to a `*.remove(x)` RNA function in the same scope, with no reassignment. That read raises `ReferenceError`. | A flow walk like `poll_checks.rs`; the list of invalidating `remove` functions (the 80 `invalidate()` calls, readable from source) | warn | Low for the variable itself. Aliases (`y = x`, then `remove(x)`, then `y.name`) may crash rather than raise; reporting them is a bonus. |
| `blender-unprotected-timer` | A timer callback whose body has a call that may raise (any `bpy.ops`, any fact-bearing call) outside a `try` that catches it. An escape unregisters the timer silently. | Facts plus handler matching (below) | warn | Medium. Many timers are one-shot (return `None`) and do not care. Report only for callbacks that can return a float. |
| `blender-escaping-exception` | In `execute` / `invoke` / `modal` and in handlers: a call whose facts say it may raise X, not caught by an enclosing `except` whose type covers X | Facts in stubs (9.3); handler type resolution | **ignore** (opt-in) | High if all facts count. Mitigations below. |
| `blender-poll-raises` | A `poll` whose body can raise. It fails silently on every redraw, which is often intended (`except AttributeError: return False` is common; `poll_checks.rs` already treats a raise as a failed poll). | Same | ignore | High; mostly intentional. Probably not worth it. |

**Handler matching.**
- ty's semantic index gives the `try` nesting but not the handler types (section 7). The Blender walk can read
  them as ruff's AST plus ty inference of each `except` expression (a class or a tuple of classes), and test the
  fact's exception class with ty's subclass relation.
- A bare `except:` or `except BaseException` / `Exception` catches all.
- A `raise` inside the handler re-raises: the handler body is checked like the try body.
- `with` statements whose context manager suppresses (`contextlib.suppress(X)`) count as handlers. ty already
  treats `with` as an exception context for flow (`except_handlers.rs:42-44`).

**How deep to look.**
- First only calls in the entry point's own body.
- Then one level into the add-on's own functions in the same add-on, as deal's linter does (section 8): a call to
  an add-on function inherits the facts of the Blender calls in its body that it does not catch. Store this as a
  per-function salsa query.
- Deeper or recursive propagation needs a fixpoint over the call graph. That is not worth it before the
  one-level version has shown its signal.

**Generic exceptions.** Ignore them, as CodeQL does (`Exceptions.qll:4-8`):
- `TypeError` / `ValueError` from argument conversion are type errors that ty already reports.
- `AttributeError` on `None` is ty's `possibly-missing-attribute` / never-none work.
- `ReferenceError` is `blender-use-after-remove`.
- `KeyError` / `IndexError` from `bpy.data.x["name"]` and other collection subscripts are a judgement call. They
  are common in add-ons (`bpy.data.objects["Cube"]`) and usually intended. Count them only under a sub-option,
  and suggest `.get()`.
- `MemoryError` and `KeyboardInterrupt`: never.

**Mitigations for `blender-escaping-exception`:**
- Report only facts of `kind` `report`, `pyerr` with *state* conditions, and `bpy.ops`. Leave out argument
  validation.
- Do not report `bpy.ops` calls already guarded by an `if bpy.ops.x.poll():` or by a poll narrowing ty-blender
  knows (`blender-narrowed-by-poll` machinery). The guard removes the poll failure but not operator errors, so keep
  those behind a sub-option.
- One diagnostic per call site, naming the exception and the first message, with the fact's evidence as a
  secondary note ("`rna_main_api.cc:140`").
- `# ty: ignore[blender-escaping-exception]` as usual.

**Tests.**
- Each rule gets feature-test markers in `tests/typecheck/features/<new feature>/`, with `_expected/` stubs carrying
  the facts. `check:oracle` would need to understand the decorator, or skip with `oracle-skip`.
- `check:load` probes confirm the runtime claims, e.g. that an `execute` which raises yields `{'FINISHED'}` and an
  undo step.

## 10. What was verified and what is inferred

- **Verified by reading the source** (file:line given in place):
  - every exception site and count in section 3;
  - the `FUNC_USE_REPORTS` gating;
  - the report levels;
  - the invalidation behaviour and `WITH_PYTHON_SAFETY` default;
  - the read-only callback write check and its callback list;
  - each row of section 5's "what happens" column;
  - ty's `try` modelling and rule list;
  - ruff's rule codes;
  - the rst `:raises` count;
  - fake-bpy's field parser;
  - the missing `use_reports` in `bpy.types.Function`.
- **Verified by experiment:**
  - stock ruff 0.17.5 `DOC501/502`, `BLE001`, `E722`, `S110` and `SIM105` behaviour, and pydoclint 0.12.0 Sphinx
    parsing, on `exceptions-research/exp/addon.py`;
  - the two counting scripts (`count_pyerr.py`, `reports_scan.py`);
  - PyPI metadata (versions, dates, licences).
- **Inferred, not run:**
  - an `execute`/`invoke`/`modal` that raises ends with `OPERATOR_FINISHED` and pushes undo. This was read from
    the result parameter's default and `wm_operator_exec`, and should be confirmed by a `check:load` probe;
  - a nested Python operator's exception reaches a `bpy.ops` caller as `RuntimeError`;
  - classes stay registered after a failing `register()`;
  - the size of the upstream patch;
  - the regex scan's split of 257 / 57 / 51 (the libclang walk would refine it);
  - semgrep's lack of type-aware flow in the open engine;
  - false-positive levels.
- **Unverified:** the discuss.python.org threads (host unreachable; summarised from search snippets); the academic
  papers (abstracts in search results only); exception-control's licence.

## 11. Sources

Blender 5.2 (`.cache/blender-src/5.2-src`):
- `source/blender/python/intern/bpy_rna.cc`, `bpy_rna.hh`, `bpy_capi_utils.cc`, `bpy_operator_function.cc`,
  `bpy_app_handlers.cc`, `bpy_app_timers.cc`, `bpy_msgbus.cc`, `bpy_props.cc`, `bpy_rna_callback.cc`, `bpy_driver.cc`
- `source/blender/python/mathutils/mathutils.cc`, `mathutils.hh`; `python/gpu/gpu_py.cc`;
  `python/bmesh/bmesh_py_types.cc`, `.hh`
- `source/blender/makesrna/RNA_types.hh`; `makesrna/intern/makesrna.cc`, `rna_wm.cc`, `rna_wm_api.cc`, `rna_ui.cc`,
  `rna_main_api.cc`, `rna_rna.cc`, `rna_access.cc`, `rna_ID.cc`
- `source/blender/blenkernel/BKE_report.hh`; `windowmanager/intern/wm_event_system.cc`; `CMakeLists.txt`
- `scripts/modules/addon_utils.py`, `_bpy_types.py`, `_rna_info.py`; `doc/python_api/sphinx_doc_gen.py`
- `doc/python_api/rst/info_gotchas_crashes.rst`, `info_gotchas_operators.rst`, `info_quickstart.rst`

This repo:
- `prototypes/source_stubs/libclang/returns.py`; `.cache/source-stubs/5.2/makesrna/facts.json`,
  `libclang/returns.md`
- `.cache/bpy-rst/5.2`, `.cache/bpy-stubs/5.2`, `.cache/bpy-stubs-builtin/5.2`
- `fake-bpy-module/src/fake_bpy_module/analyzer/directives.py`
- `ty-blender/ruff-blender/crates/ty_python_core/src/builder.rs`, `builder/except_handlers.rs`, `predicate.rs`
- `crates/ty_python_semantic/src/types/dedicated/blender/` (`lints.rs`, `poll_checks.rs`, `walk.rs`) and
  `resources/lint_docs/`
- `crates/ty/docs/rules.md`; `crates/ruff_linter/src/codes.rs`, `rules/pydoclint/rules/check_docstring.rs`
- `scripts/blender/probe_never_none.py`, `scripts/check_load.py`, `tests/typecheck/README.md`

Standards and conventions (read as raw files on GitHub):
- PEP 484, *Exceptions*: [peps/pep-0484.rst](https://github.com/python/peps/blob/main/peps/pep-0484.rst)
- Typing spec, `NoReturn` / `Never`: [docs/spec/special-types.rst](https://github.com/python/typing/blob/main/docs/spec/special-types.rst)
- Typing guide, docstrings in stubs: [docs/guides/writing_stubs.rst](https://github.com/python/typing/blob/main/docs/guides/writing_stubs.rst)
- typeshed: [CONTRIBUTING.md](https://github.com/python/typeshed/blob/main/CONTRIBUTING.md)
- Sphinx info fields: [doc/usage/domains/python.rst](https://github.com/sphinx-doc/sphinx/blob/master/doc/usage/domains/python.rst)
- numpydoc: [doc/format.rst](https://github.com/numpy/numpydoc/blob/main/doc/format.rst)
- Google style guide: [pyguide.md](https://github.com/google/styleguide/blob/gh-pages/pyguide.md)
- Typing-forum threads (search snippets only; host unreachable):
  [Extend type hints to cover exceptions](https://discuss.python.org/t/extend-type-hints-to-cover-exceptions/23788),
  [PEP 484: When will we have syntax for Exceptions?](https://discuss.python.org/t/pep-484-when-will-we-have-syntax-for-exceptions/26936),
  [Statically tracked exceptions ... to support EAFP](https://discuss.python.org/t/statically-tracked-exceptions-in-pythons-type-system-to-support-eafp/110061)

Tools:
- pyright: [docs/configuration.md](https://github.com/microsoft/pyright/blob/main/docs/configuration.md)
- CodeQL: [Exceptions.qll](https://github.com/github/codeql/blob/main/python/ql/lib/semmle/python/types/Exceptions.qll),
  [python/ql/src/Exceptions](https://github.com/github/codeql/tree/main/python/ql/src/Exceptions),
  [CLI licence](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md)
- deal: [docs/basic/exceptions.md](https://github.com/life4/deal/blob/master/docs/basic/exceptions.md),
  [docs/details/stubs.md](https://github.com/life4/deal/blob/master/docs/details/stubs.md),
  [deal/linter/_stub.py](https://github.com/life4/deal/blob/master/deal/linter/_stub.py)
- pydoclint: [docs/config_options.md](https://github.com/jsh9/pydoclint/blob/main/docs/config_options.md)
- pylint: [features.rst](https://github.com/pylint-dev/pylint/blob/main/doc/user_guide/checkers/features.rst),
  [extensions.rst](https://github.com/pylint-dev/pylint/blob/main/doc/user_guide/checkers/extensions.rst)
- Pyre/Pysa: [pysa_basics.md](https://github.com/facebook/pyre-check/blob/main/documentation/website/docs/pysa_basics.md)
- pytype: [README.md](https://github.com/google/pytype/blob/main/README.md)
- semgrep: [LICENSE](https://github.com/semgrep/semgrep/blob/develop/LICENSE)
- exception-control: [README.md](https://github.com/Julynx/exception-control/blob/main/README.md)
- PyPI JSON metadata for deal, pydoclint, darglint, flake8-raise, pytype, pyre-check, semgrep, returns, pylint,
  tryceratops (versions, release dates, licences)
- Papers (abstracts via search): [Fromherz, Ouadjaout, Miné](https://hal.sorbonne-universite.fr/hal-01782390v1/document),
  [Monat, Ouadjaout, Miné, ECOOP 2020](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2020.17)

Not reachable from this session: discuss.python.org, peps.python.org, the GitHub API for repositories not attached
(raw.githubusercontent.com and pypi.org worked).
