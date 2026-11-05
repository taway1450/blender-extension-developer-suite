# What the leftover bpy_symbols markers need

Research note, 2026-11-06, for [#28](https://github.com/taway1450/blender-extension-developer-suite/issues/28)
(map [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). The decisions of map #1
(#2–#12) and of the closed tickets of map #21 are taken as given, especially:

- stub bugs are fixed in the stub generators, not in the checker;
- edits to upstream ty files stay minimal (one-line hooks into fork-owned files).

Conventions:

- Every fact has a `path:line` source.
  - `ruff-blender/` is `ty-blender/ruff-blender/crates/`, and `blender/` is the Blender source
    `.cache/blender-src/main/` (same code in `5.2/` unless noted).
  - `features/` is `tests/typecheck/features/bpy_symbols/`, and `expected/<gen>` is
    `tests/typecheck/expected/<gen>/main.txt`.
  - `stubs-builtin/` is `.cache/bpy-stubs-builtin/main/`, and `stubs-fake/` is `.cache/bpy-stubs/main/`.
  - `fbm/` is the `fake-bpy-module` submodule's `src/`.
- Diagnostic messages are quoted from `.cache/typecheck-results/5.2/<gen>/ty.txt`, the last full run with
  messages; `expected/<gen>` for main records the same codes on the same lines.
- Nothing was run: every finding comes from reading the code and the recorded results in `expected/` and
  `.cache/typecheck-results/`. **Recommendation** marks my own proposals.

Out of scope here, owned elsewhere:

- `assert_type(s.offset, Vector)` in every `generated/sym_*` add-on, and all of `sym_mathutils`: vector subtypes,
  [#25](https://github.com/taway1450/blender-extension-developer-suite/issues/25).
- Every `bpy.ops.<category>.<name>(...)` marker (`generated/sym_*`, `sym_bpy_extras/check_sym_bpy_extras.py:27-29`):
  operator calls, [#23](https://github.com/taway1450/blender-extension-developer-suite/issues/23).

`sym_negative` itself has no failing marker on either generator. The star-import markers the ticket mentions are
in `generated/sym_star/check_sym_star.py:47-50`.

---

## 1. Answer

| Leftover | Fails today (builtin / fake-bpy-module) | Fix location (**Recommendation**) |
| --- | --- | --- |
| `from bpy.types import *` binds `PropertyGroup` / `Operator` | both: 2 × `unused-ignore-comment` (`sym_star/check_sym_star.py:49-50`) | **checker**: a one-line hook in `reachability.rs`, not an `__all__` (section 2) |
| `@persistent` returns the function | both: `unused-ignore-comment` on `on_load_post(1)` | **stub generators**: `persistent` becomes an identity decorator (section 3) |
| `load_post` handler arguments | builtin: `unused-ignore-comment` on `append(one_argument)`; fake: `invalid-argument-type` × 2 on `frame_change_post` | **the marker is wrong**: a one-argument handler works. Fix the test, then the stub generators (section 3) |
| `ImportHelper` / `ExportHelper` `filepath`, `check_existing` | both: unresolved / `Unknown` | **stub generators** (Blender's `sphinx_doc_gen.py` drops the mixins' annotations) (section 4.1) |
| `invalid-method-override` on `class X(Operator, ImportHelper)` | both: 3 × | **stub source**: the mixins' `invoke` docstrings say `set[str]` (section 4.2) |
| `@orientation_helper(...)` turns the class into `type` | builtin: `invalid-type-form` × 2, `invalid-argument-type` × 2, assertions `Unknown` | **stub source**: its `:rtype:` must keep the class (section 4.3) |
| `axis_forward` / `axis_up` from `@orientation_helper` | both: missing | **checker**: a third property origin in the fork's `member.rs`, no upstream edit (section 4.4) |

No leftover needs a named exception, but one marker must change (section 3.2).

## 2. `from bpy.types import *`

### 2.1 Runtime

- `bpy.types` is a C module whose classes come from a module-level `__getattr__` that looks the name up in RNA
  (`blender/source/blender/python/intern/bpy_rna.cc:9127-9161`). `__dir__` lists every RNA struct
  (`bpy_rna.cc:9163-9183`).
- Its `__dict__` holds only the internal base types, put there at creation
  (`bpy_rna.cc:9248-9264`): `bpy_struct_meta_idprop`, `bpy_struct`, `bpy_prop`, `bpy_prop_array`,
  `bpy_prop_collection`, `bpy_prop_collection_idprop`, `bpy_func` (their `tp_name`s).
- The module has no `__all__`: `__getattr__("__all__")` finds no struct and falls back to
  `PyObject_GenericGetAttr`, which raises (`bpy_rna.cc:9147-9158`). A star import without `__all__` binds the
  public keys of `__dict__`, not `dir()`, so only those base types are bound. This matches the runtime fact in
  `features/README.md` and the comment in `check_sym_star.py:15-17`.

### 2.2 What ty does with the stubs

- Both stubs define every class at module level in `bpy/types/__init__.pyi` with no `__all__`
  (`stubs-builtin/bpy/types/__init__.pyi`, `stubs-fake/bpy-stubs/types/__init__.pyi`), so ty binds all of them.
- ty limits a star import only through `__all__`: the semantic index adds a definition per exported name
  (`ruff-blender/ty_python_core/src/builder.rs:4203-4244`), each guarded by a `StarImportPlaceholder` predicate,
  and that predicate turns `AlwaysFalse` when the name is not in the exporter's `__all__`
  (`ruff-blender/ty_python_semantic/src/reachability.rs:2020-2036`).

### 2.3 Options

1. **`__all__` in the stubs** (what the ticket suggests). It would make the two markers pass on every type
   checker. But `__all__` is also the stub's library interface: ty's auto-import follows it strictly
   (`ruff-blender/ty_ide/src/symbols.rs:1261-1270`, used by `all_symbols.rs:65`), so `PropertyGroup`,
   `Operator`, `Panel`, ... would no longer be offered as auto-imports from `bpy.types`. Pyright/Pylance read
   `__all__` the same way. A stub cannot say "public, but not bound by `*`", so this trades a rare import form
   (PEP 8 discourages it) for a regression in the most common editor action. The stubs are not wrong about
   what `bpy.types` *has*; the gap is a runtime quirk of a lazy module.
2. **Checker hook (Recommendation).** In `reachability.rs`, at the top of the `StarImportPlaceholder` arm
   (`reachability.rs:2020`), one line:

   ```rust
   if blender::hides_star_import(db, program_file, symbol.name()) { return Truthiness::AlwaysFalse; }
   ```

   `hides_star_import` goes into the fork's `dedicated/blender/symbols.rs`. It is true when the referenced file
   is Blender's `bpy.types` (the existing `blender_module_name` check, `symbols.rs:17-25`, which also rejects a
   first-party `bpy/types.py`) and the name is not one of the base types above. The names then become unbound
   in the importer, so `unresolved-reference` is reported exactly as for an `__all__` miss, and auto-import is
   untouched.
3. **Named exception.** Cheap, but the hook costs one upstream line and keeps the map's "every marker passes".

This is a checker rule, not a stub fix, because the stub language cannot express the runtime without breaking
the interface. It is the one place in this ticket where the map rule "stub bugs go to the generators" does not
apply, and the reason belongs in the spec.

## 3. `bpy.app.handlers`

### 3.1 Runtime

- **`persistent`** is a type whose `tp_new` tags the function and returns it unchanged
  (`blender/source/blender/python/intern/bpy_app_handlers.cc:211-247`, `Py_INCREF(value); return value;` at
  `:241-242`). Its docstring says `:type: type` (`bpy_app_handlers.cc:185-187`).
- **How a handler is called** (`bpy_app_generic_callback`, `bpy_app_handlers.cc:441-480`):
  - Blender builds two tuples: `args_all` with 2 items (the pointers, padded with `None`) and `args_single` with
    the first pointer (or `None`) (`:450-466`).
  - `choose_arguments` passes `args_single` to a plain Python function whose `co_argcount == 1`, and
    `args_all` to everything else, methods and other callables included (`:426-436`, used at `:475`).
  - The same code is in 4.2 and 5.2 (`.cache/blender-src/4.2/.../bpy_app_handlers.cc:343-349`,
    `5.2/...:422-428`).
- **`load_post`** and the other file handlers pass one pointer, the file path as a primitive string
  (`blender/source/blender/blenkernel/intern/callbacks.cc:76-85`; called from
  `windowmanager/intern/wm_files.cc:785`). So:
  - `def h(filepath)` gets `("file.blend",)`;
  - `def h(filepath, _unused)` and `def h(*args)` get `("file.blend", None)`;
  - `def h()` gets two arguments and raises `TypeError`.
- Handlers without pointers (`load_factory_startup_post`, `version_update`, ...) get `(None,)` or
  `(None, None)` by the same rule, so a zero-argument handler fails there too.

**So a one-argument `load_post` handler works.** The marker
`bpy.app.handlers.load_post.append(one_argument)  # ty: ignore[invalid-argument-type]`
(`features/sym_handlers/check_sym_handlers.py:31-32`) and its comment are wrong, and so is the reference stub
delta `load_post: list[Callable[[str, None], None]]` (`features/sym_handlers/_expected/stubs/bpy.app.handlers.pyi:6`).
`check:load` does not catch it, because nothing fires a handler (`scripts/blender/load_feature_addons.py:54-76`).

### 3.2 Test changes (Recommendation)

- Turn the marker around: `load_post.append(one_argument)` is accepted (no ignore), and add the real error,
  a zero-argument handler:

  ```python
  def no_arguments() -> None: ...
  bpy.app.handlers.load_post.append(no_arguments)  # ty: ignore[invalid-argument-type]
  ```

- Reference stub delta: `load_post: list[Callable[[str], None] | Callable[[str, None], None]]`.
- README runtime facts: say a handler gets one argument when it takes one, two otherwise.
- Optionally a `check:load` probe that calls `bpy.ops.wm.read_homefile()` with both handler shapes appended,
  so the runtime claim is checked by the harness.

### 3.3 What the stubs say

| Symbol | builtin | fake-bpy-module |
| --- | --- | --- |
| `persistent` | `persistent: type` (`stubs-builtin/bpy/app/handlers/__init__.pyi`, last line) | `persistent: typing.Any` (`stubs-fake/bpy-stubs/app/handlers/__init__.pyi:193`) |
| `load_post` | `list[Callable[[str], None]]` | `list[Callable[[Scene], None]] \| list[Callable[str, None]]` (`:151-154`) |
| `frame_change_post` | `list[Callable[[Scene, Depsgraph], None] \| Callable[[Scene], None]]` | `list[Callable[[Scene, Depsgraph], None] \| Callable[[Scene], None]] \| list[Callable[[Scene], None]]` (`:123-129`) |
| no-pointer handlers | `list[Callable[[], None]]` | `list[Callable[None]] \| list[Callable[[Scene], None]]` |

How each failure follows:

- `on_load_post(1)` passes on both because `persistent(f)` is `type` (builtin: calling an instance of `type`
  accepts anything) or `Any` (fake) — the function's signature is lost.
- builtin accepts `append(one_argument)` (correctly, see 3.1), so the wrong marker's ignore is unused. fake
  happens to reject it, for the wrong reason (the malformed `Callable[str, None]`).
- fake rejects `frame_change_post.append(on_frame_change)`: appending to a union of two list types needs an
  argument assignable to both, and the second, `list[Callable[[Scene], None]]`, rejects a two-parameter function.

Sources of these types:

- Both generators read the rst that Blender's `doc/python_api/sphinx_doc_gen.py` writes, and that takes the
  handler types from the C docstrings: `PYDOC_FILEPATH_LOAD_TYPE` is `list[Callable[[str], None]]`
  (`bpy_app_handlers.cc:41-44`), `PYDOC_HANDLER_TYPE_NONE` is `list[Callable[[], None]]` (`:91`).
- fake-bpy-module then prepends `list of callable[bpy.types.Scene]` to every handler but `persistent`
  (`fbm/fake_bpy_module/transformer/bpy_module_tweaker.py:86-99`), a leftover from Blender versions whose
  docs had no handler types; its refiner turns `Callable[[str], None]` into `Callable[str, None]`. It already has
  a mod file for two handlers (`fbm/mods/common/analyzer/update/bpy.app.handlers.mod.rst`).

### 3.4 Fixes (Recommendation)

All in the stub generators:

- **Handler types, at the source:** the docstring macros in Blender's `bpy_app_handlers.cc` (the `blender`
  submodule fork; both generators inherit them). Each one-pointer handler becomes
  `list[Callable[[T], None] | Callable[[T, None], None]]`, each two-pointer handler stays as it is, each
  no-pointer handler becomes `list[Callable[[None], None] | Callable[[None, None], None]]`. Returns could be
  `object`, since Blender ignores them. This is upstreamable to Blender. The 5.2 stubs need the same change on
  the fork's 5.2 branch.
- **fake-bpy-module:** drop the blanket `Scene` insertion when the data already has a documented type, and keep
  `Callable[[str], None]` intact through the refiner (or pin the handler types in the mod file with
  `:mod-option: skip-refine`, as the existing entries do).
- **`persistent`:** no rst `:type:` can say "returns its argument", so each generator special-cases it as
  `def persistent(func: _F, /) -> _F` with `_F = TypeVar("_F", bound=Callable[..., object])`:
  - builtin: in `doc/python_api/sphinx_stub_gen.py`, or by documenting it in `sphinx_doc_gen.py` as a function;
  - fake-bpy-module: a `.. function:: persistent(func)` entry in the handlers mod file.

The checker needs nothing for handlers.

## 4. `bpy_extras.io_utils`

### 4.1 `filepath` and `check_existing`

- **Runtime:** the mixins declare them as Annotated properties in their bodies:
  `ExportHelper.filepath: StringProperty(...)`, `check_existing: BoolProperty(...)`
  (`blender/scripts/modules/bpy_extras/io_utils.py:44-56`), `ImportHelper.filepath: StringProperty(...)`
  (`io_utils.py:119-126`).
- **Stubs:** neither has them (`stubs-builtin/bpy_extras/io_utils/__init__.pyi:11-18`,
  `stubs-fake/bpy_extras-stubs/io_utils/__init__.pyi:8-50`), so `exp.filepath` is `unresolved-attribute`
  (`.cache/typecheck-results/5.2/builtin/ty.txt:117-119`).
- **Why:** Blender's `pyclass2sphinx` documents only functions and descriptors from the class `__dict__`, and
  skips every key starting with `_`, so `__annotations__` is never written
  (`blender/doc/python_api/sphinx_doc_gen.py:1916-1976`, filter at `:1938`). Both generators consume that rst.
- **Would the checker type them if the stubs declared them?** Yes. The annotation takeover and
  `property_declaration` recognise a `bpy.props` call by the callee's resolved symbol, in any file
  (`ruff-blender/ty_python_semantic/src/types/dedicated/blender/properties.rs:253-345`, `symbols.rs:28-38`), and
  `ImportHelper` is a plain class, so the off-host rule keeps its annotations
  (`dedicated/blender/member.rs:129-148`). No decorator- or mixin-specific support is needed for these two.
- **Fix (Recommendation):** `pyclass2sphinx` writes an `.. attribute::` with a `:type:` for each
  `_PropertyDeferred` in a pure-Python class's `__annotations__`; it runs inside Blender, so it can read the
  deferred's function and keywords and give the value type (`str`, `bool`, ...). That fixes both generators.
- **The form decides what operator calls see.** A plain `filepath: str` types the attribute for this ticket's
  markers, but it is not a property declaration, so an operator-call signature built from the class's properties
  ([#23](https://github.com/taway1450/blender-extension-developer-suite/issues/23)) would not offer
  `filepath=` (`check_sym_bpy_extras.py:27-29`). A form that keeps the property and still reads as `str` for stock
  tools is `filepath: Annotated[str, StringProperty(subtype="FILE_PATH", ...)]`, with `property_declaration`
  taught to look inside `Annotated` (a fork-owned file). The choice belongs to #23 (see the surfaced question).

### 4.2 `invalid-method-override` on `class X(Operator, ImportHelper)`

- ty reports "`Operator.invoke` is incompatible with `ImportHelper.invoke`" for all three operators on both
  generators (`.cache/typecheck-results/5.2/builtin/ty.txt:105-107`).
- `Operator.invoke` returns `set[Literal["RUNNING_MODAL", ...]]`
  (`stubs-builtin/bpy/types/__init__.pyi:19207`; `stubs-fake/bpy-stubs/types/__init__.pyi`, `Operator.invoke`),
  the mixins' `invoke` returns `set[str]` (`stubs-builtin/bpy_extras/io_utils/__init__.pyi:13,17`). `set` is
  invariant, so the first base's method does not override the later one's.
- Source: the docstrings `:rtype: set[str]` at `io_utils.py:72`, `:137` and `:154`.
- **Fix (Recommendation):** write the operator return type there,
  `set[Literal['RUNNING_MODAL', 'CANCELLED', 'FINISHED', 'PASS_THROUGH', 'INTERFACE']]`, what the methods
  really return (`{'RUNNING_MODAL'}`, ...). Docstring fix in the Blender fork, both generators follow.

### 4.3 `@orientation_helper(...)` loses the class

- Runtime: the decorator adds two annotations and returns the same class (`io_utils.py:190-258`, `return cls`
  at `:256`).
- Its docstring says `:rtype: Callable[[type], type]` (`io_utils.py:200`), so the builtin stub says so
  (`stubs-builtin/bpy_extras/io_utils/__init__.pyi:20`). ty applies a class decorator's return type to the
  class name (`ruff-blender/ty_python_semantic/src/types/infer/builder/class.rs:324-325`), so the decorated
  operator becomes an instance of `type`: `invalid-type-form` on `imp: SYM_BPY_EXTRAS_OT_import`,
  `invalid-argument-type` on `register_class(cls)`, and `Unknown` for every assertion on `imp` and `mod`
  (`ty.txt:108-116`). fake-bpy-module's `Callable[typing.Any, typing.Any]`
  (`stubs-fake/bpy_extras-stubs/io_utils/__init__.pyi:92-95`) is no valid form, and ty keeps the class.
- **Fix (Recommendation):** the stub must be an identity class decorator,
  `-> Callable[[_C], _C]` with `_C = TypeVar("_C", bound=type)`. The rst cannot write a TypeVar, so this is a
  generator special case like `persistent` (or `CLASS_BASES`-style override table in `sphinx_stub_gen.py`;
  fake-bpy-module: a mod file).

### 4.4 `axis_forward` / `axis_up`

- Runtime: `orientation_helper` puts `EnumProperty(items=<six axes>, default=..., update=...)` into the
  decorated class's `__annotations__` (`io_utils.py:221-254`). No class body declares them.
- No stub can express this: a decorator that adds attributes would need an intersection type, which Python
  typing does not have. So this one **needs its own checker support**; it does not follow from Annotated
  properties.
- **Where (Recommendation):** a third origin in `instance_property` (`dedicated/blender/member.rs:44-65`),
  beside Annotated and Registered properties: when a class in the MRO is decorated with a call whose callee
  resolves to `bpy_extras.io_utils.orientation_helper`, it declares `axis_forward` and `axis_up` as static enums
  of `X, Y, Z, -X, -Y, -Z`.
  - Reads already reach `instance_property` through the existing `on_load` hook when ty finds no member
    (`member.rs:297-323`), writes through `on_store` (`member.rs:331`), so `imp.axis_up = "W"` reports
    `invalid-assignment` and completions can list them. **No new upstream hook.**
  - Read the decorator syntactically from the class node and its callee type from the class definition's
    inference, as `property_declaration` does; `StaticClassLiteral::decorators` is private
    (`ruff-blender/ty_python_semantic/src/types/class/static_literal.rs:800`) and gives the decorator's
    result, not its callee.
  - Symbol recognition only knows `bpy` / `bpy.*` (`symbols.rs:17-25`); it must also accept `bpy_extras.*`.
  - `PropertyDeclaration` (`properties.rs:75-91`) gets a constructor for a synthesised enum.
  - Needs 4.3 first: with `Callable[[type], type]` there is no class left to look up.
  - #23 must use the same origin, so `import_file(axis_up="Z")` type-checks (`check_sym_bpy_extras.py:27-28`).

## 5. Order and dependencies

1. Test fixes: the handler marker, its reference stub delta and README fact (section 3.2).
2. Stub source fixes in the Blender fork (main and 5.2): handler docstrings, `io_utils` `invoke` rtypes,
   `pyclass2sphinx` annotations. Then generator special cases: `persistent`, `orientation_helper`, fake-bpy-module's
   handler tweaker.
3. Checker: the star-import hook (independent), then the decorator origin for `axis_*` (after step 2).

After all three, every non-vector, non-`bpy.ops` bpy_symbols marker passes on both generators, with no named
exception.
