# Operator calls and operator properties in Blender's own code

Research for [#72](https://github.com/taway1450/blender-extension-developer-suite/issues/72), map
[#67](https://github.com/taway1450/blender-extension-developer-suite/issues/67), 2026-11. Trimmed on 2026-11-18 to
the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.
Blender's source was read at main `dc491af090` (`.cache/blender-src/main`). All the gaps it found are fixed on main.

## 1. Positional execution context and undo flag

### What Blender accepts

`bpy.ops.<cat>.<name>` returns a C `BPyOpFunction` (`scripts/modules/bpy/ops.py:18-23`, `_op_create_function`), whose
`tp_call` parses the positional arguments in `bpy_op_parse_args`
(`source/blender/python/intern/bpy_operator_function.cc:115-150`):

- any number of positional arguments is walked in order; a `str` sets the execution context (once), a `bool` **or
  `int`** (`PyBool_Check || PyLong_Check`) sets the undo flag (once);
- a string after the flag raises `ValueError("string arg must come before the boolean")`; anything else, or a third
  argument, raises `ValueError("1-2 args execution context is supported")`;
- the context string is validated later (unknown context: `TypeError`).

So the accepted forms are `()`, `(context)`, `(undo)`, `(context, undo)`, all positional, then keywords. The docstring
says the same: `BPyOpFunction(context='EXEC_DEFAULT', undo=False, **kwargs)` (`bpy_operator_function.cc:739`).

### Why Blender's stubs lacked it

Blender's stub generator writes built-in operators as `def call_menu(*, name: str='')`: keyword-only, no context,
no undo flag (`.cache/bpy-stubs-builtin/main/bpy/ops/wm/__init__.pyi:17`). It is generated from the RST that
`doc/python_api/sphinx_doc_gen.py:3143` writes: `".. function:: {name}({'*, ' if args}{args})"` with the comment
"All operator arguments are keyword only". fake-bpy-module writes
`__new__(cls, execution_context=None, undo=None, /, *, ...)`.

### The two places a fix could go

- **In the checker**: give a built-in operator the same protocol as an add-on operator, with the keywords taken
  from the stub's keyword-only parameters. This needs to work in files outside any add-on (`scripts/startup`).
  With fake-bpy-module it replaces its `__new__`, which also tightens its `int | str | None` context to the literal
  set.
- **In the stub generator**: `sphinx_doc_gen.py:3143` writes `(execution_context: str = 'EXEC_DEFAULT', undo: bool =
  False, /, *, ...)` and `sphinx_stub_gen.py` types it. One small commit on the Blender fork, but it changes the
  published RST/HTML docs of every operator, and a function signature cannot say "undo alone" without an overload.

The checker route won: it needs no stub change, gives one behaviour for both stub flavours and for add-on and
built-in operators, and keeps the literal context set.

## 2. Facts behind the operator-properties gaps

- **An operator property named `properties`.** At runtime `Operator.__getattribute__`
  (`scripts/modules/_bpy_types.py:1103-1108`) returns an own property before any `Operator` member. So a declared
  property named `properties` (`WM_OT_operator_presets_cleanup.properties: CollectionProperty(...)`,
  `presets.py:972`) shadows the built-in `self.properties`, and the checker must yield to it.
- **`template_popup_confirm("", ...)`** (no operator, only a cancel button, `bl_extension_ops.py:3797`) is valid and
  must stay unrefined, not `blender-unknown-operator`.
- C and Python built-in operators are both in the generated `bpy.ops` stubs, so "C operators" is never a cause of a
  missing operator.

## 3. Other operator facts

- **`Operator.description` may return `None`:** the RNA function clears `PROP_NEVER_NULL` on its `result`
  (`makesrna/intern/rna_wm_api.cc:1425-1426`) and `rna_operator_description_cb` maps a null result to `""`
  (`rna_wm.cc:1785-1786`). Blender's stub says `-> str` (`bpy/types/__init__.pyi:21600`); it should be
  `str | None`. A stub-generator fact.
