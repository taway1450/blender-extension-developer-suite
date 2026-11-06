# Operator calls and operator properties in Blender's own code

Research for [#72](https://github.com/taway1450/blender-extension-developer-suite/issues/72), map
[#67](https://github.com/taway1450/blender-extension-developer-suite/issues/67). Evidence: `check:blender main`
with Blender's own stubs (`.cache/analysis/main-builtin.txt`, Blender main `dc491af090`), the ty fork at
`ty-blender/ruff-blender`, Blender's source in `.cache/blender-src/main`.

## Answer in short

1. **Positional execution context (78 diagnostics, 32 in shipped code).** `operator_calls` already builds the right
   signature, but only for the operators of the add-on that makes the call. Every one of the 78 calls is to a
   **built-in** operator (`wm.call_menu`, `screen.userpref_show`, `view3d.*`, `wm.open_mainfile`...), whose type comes
   straight from the stub, and Blender's stub generator writes those as `def call_menu(*, name: str='')`: keyword-only,
   no context, no undo flag. fake-bpy-module writes `__new__(cls, execution_context=None, undo=None, /, *, ...)` and
   has none of these diagnostics.
2. **`OperatorProperties` in Blender's code (~49 diagnostics).** `operator_properties` is built and does work for
   Blender's own operators (`layout.operator("transform.mirror").constraint_axis` is typed from the stub). The
   leftovers come from five separate gaps, none of them "C operators" or "Blender's operators instead of an add-on's":
   the `description(cls, context, properties)` callback parameter (32), a conditional idname (5), a sink missing from
   the table (`template_popup_confirm`, 3), the read type of a built-in boolean array (6), and a property named
   `properties` (1). The rest is in `doc/` and `tests/`, outside any add-on.

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
This matches the `operator_calls` README's runtime facts and the two overloads `operators.rs` already builds.

### Where the signature comes from today

- `ty_python_semantic/src/types/dedicated/blender/operators.rs`, `operator_type` (lines ~237-310): builds the protocol
  with `__call__` overloads `(self, execution_context: Literal[EXECUTION_CONTEXTS] = ..., undo: bool = ..., /, *,
  <props>)` and `(self, undo: bool, /, *, <props>)`, plus `poll`, `idname`, `idname_py`, `get_rna_type`.
- It is reached only through `operators::module_attribute` (hooked in `member.rs:417`), which returns `None` unless
  `operators_of(db, file)` finds the file's add-on **and** `operators.get(category, name)` finds the operator among
  that add-on's own operators. A built-in operator, or any call from a file outside an add-on (all of
  `scripts/startup`), keeps the stub's attribute.
- The stub: `.cache/bpy-stubs-builtin/main/bpy/ops/wm/__init__.pyi:17`,
  `def call_menu(*, name: str='') -> set[rna_enum_operator_return_items]: ...`. It is generated from the RST that
  `doc/python_api/sphinx_doc_gen.py:3143` writes: `".. function:: {name}({'*, ' if args}{args})"` with the comment
  "All operator arguments are keyword only". `sphinx_stub_gen.py` turns that RST into the `.pyi`.

### The 78 calls

All 78 `ops:positional-exec-context` diagnostics are calls to built-in operators with a **literal** context, e.g.
`bpy.ops.wm.call_menu("INVOKE_DEFAULT", name=...)` (`bone_selection_sets.py:188`, node_wrangler `lazy_connect.py:92`),
`bpy.ops.screen.userpref_show('INVOKE_DEFAULT')` (bl_pkg, 6×), `view3d.py` (10× `'INVOKE_REGION_WIN'`),
`wm.open_mainfile` / `wm.save_mainfile` / `previews_clear` in `tests/` (some with `(context, undo)`). None passes a
non-literal context. Calls from add-ons (bl_pkg, node_wrangler) fail too, because the operators are Blender's.

### What is missing, and the two places it could go

The map settled "positional `execution_context` / `undo` in `operator_calls`". Two implementations fit:

- **In the checker** (`operators.rs`): when `module_attribute` sees a bound attribute of a `bpy.ops.<category>`
  module that is a stub function (or fake-bpy-module class), return the same protocol `operator_type` builds, with
  the keywords taken from the stub's keyword-only parameters. `builtin_operator` in `operator_properties.rs:289`
  already reads exactly those parameters from both stub flavours, so the keyword list exists. The early return on
  "no add-on" has to go for this path (files in `scripts/startup` belong to no add-on). With fake-bpy-module this
  replaces its `__new__`, which also tightens its `int | str | None` context to the literal set.
- **In the stub generator**: `sphinx_doc_gen.py:3143` writes `(execution_context: str = 'EXEC_DEFAULT', undo: bool =
  False, /, *, ...)` and `sphinx_stub_gen.py` types it. One small commit on the Blender fork, but it changes the
  published RST/HTML docs of every operator, and a function signature cannot say "undo alone" without an overload.

The checker route needs no stub change, gives one behaviour for both stub flavours and for add-on and built-in
operators, and keeps the literal context set; the marker goes in `opcall_category` (a built-in operator called with
`'INVOKE_DEFAULT'`, with `('EXEC_DEFAULT', True)`, with `True` alone, and a wrong context). Expected effect: all 78.

## 2. `OperatorProperties` left in Blender's code

How `operator_properties` resolves an idname (`operator_properties.rs`): `on_call` refines the return of a sink
listed in `ty_blender::SINKS` (`crates/ty_blender/src/operators.rs:56-85`); `argument_idname` takes a single string
literal or `X.bl_idname`; `find_operator_at` looks in the add-on, then `builtin_operator` reads the `bpy.ops` stub.
Built-in operators therefore work from any file, add-on or not. What is left:

| Gap | Diagnostics | Example | Where the fix goes |
| --- | --- | --- | --- |
| A. `Operator.description(cls, context, properties)`: the parameter keeps the stub's `OperatorProperties` | 32 (`wm.py` 27, bl_pkg 2, node_wrangler 3) | `wm.py:295` `props.data_path` | `own_properties` covers `self.properties` only; the callback parameter needs the class's own properties (`properties_type` of `class_operator`), the same refinement applied to the parameter of an overriding `description` |
| B. Conditional idname `"a" if c else "b"` | 5 (`properties_workspace.py:167`, `space_userpref.py:2656`, `bl_extension_ui.py:2012/2030/2031`) | `row.operator("wm.owner_disable" if e else "wm.owner_enable").owner_id = ...` | `literal_string` accepts exactly one literal; a union of literals could give the union of each operator's `properties_type` (here the two operators share the property) |
| C. Sink missing: `UILayout.template_popup_confirm(operator, ...) -> OperatorProperties \| None` | 3 (`wm.py:3869/3872`, `bl_extension_ops.py:3825`) | `col.template_popup_confirm("wm.link", ...).filepath = filepath` | a row in `SINKS`; note `template_popup_confirm("", ...)` (no operator, only a cancel button, `bl_extension_ops.py:3797`) is valid and must stay unrefined, not `blender-unknown-operator` |
| D. Built-in boolean / int array property reads as `Sequence[bool]` | 6 (`space_image.py:369/370/589/590`, `space_sequencer.py:976`, `space_view3d.py:1482`) | `layout.operator("transform.mirror").constraint_axis[0] = True` | `vector_value` (`operator_properties.rs:357`) only maps a union with a `mathutils` arm; a bare `Sequence[bool]` / `Sequence[int]` should read as `bpy_prop_array[...]` as for add-on properties |
| E. An operator property named `properties` | 1 (`presets.py:972`) | `WM_OT_operator_presets_cleanup.properties: CollectionProperty(...)`; `for prop in self.properties` | at runtime `Operator.__getattribute__` (`scripts/modules/_bpy_types.py:1103-1108`) returns an own property before any `Operator` member, so `own_properties` must yield to a declared property of that name |

Not operator gaps, left as they are:

- `properties_strip.py:55`: the sink call itself fails (`icon=` is a plain `str`), so no overload matches and nothing
  is refined; the assignment error follows from that one.
- `doc/python_api/examples` (`bpy.props.1.py`, `bpy.types.UIList.3.py`) and `tests/` (`bl_pyapi_idprop_datablock.py`,
  `test_blend_autoexec.py`): the operator is defined in a script that is no add-on, so neither the add-on index nor
  the stubs know it. Reported apart per the map.

Neither "C operators" nor "dynamic idnames" is a cause: C and Python built-in operators are both in the generated
`bpy.ops` stubs, and no shipped diagnostic involves an idname built at runtime.

## 3. Other operator-related diagnostics

- **`Operator.description` may return `None`** (`wm.py:501`, `invalid-return-type ... expected str, found None`):
  the RNA function clears `PROP_NEVER_NULL` on its `result` (`makesrna/intern/rna_wm_api.cc:1425-1426`) and
  `rna_operator_description_cb` maps a null result to `""` (`rna_wm.cc:1785-1786`). Blender's stub says `-> str`
  (`bpy/types/__init__.pyi:21600`); it should be `str | None`. A stub-generator fact, `api_types` material.
- **`blender-invalid-operator-property`** (1, `tests/python/bl_pyapi_idprop_datablock.py:254`): a true positive.
- **`unknown-argument` on `object.__init__`** (`anim.py:278`) and the other `too-many-positional-arguments` on
  `object.__init__`, `Gizmo.target_set_value`, `RenderEngine.update`, `Object.to_mesh`: not operator calls.
- No `blender-unknown-operator` fires on Blender main.
