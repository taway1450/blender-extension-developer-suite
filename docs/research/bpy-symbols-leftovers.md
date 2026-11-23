# What the leftover bpy_symbols markers need

Research note, 2026-11-06, for [#28](https://github.com/taway1450/blender-extension-developer-suite/issues/28)
(map [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). Trimmed on 2026-11-18 to the
rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings. The
decisions of map #1 are taken as given, especially:

- stub bugs are fixed in the stub generators, not in the checker;
- edits to upstream ty files stay minimal (one-line hooks into fork-owned files).

Conventions:

- Every fact has a `path:line` source.
  - `ruff-blender/` is `ty-blender/ruff-blender/crates/`, and `blender/` is the Blender source
    `.cache/blender-src/main/` (same code in `5.2/` unless noted).
  - `stubs-builtin/` is `.cache/bpy-stubs-builtin/main/`, and `stubs-fake/` is `.cache/bpy-stubs/main/`.
  - `fbm/` is the `fake-bpy-module` submodule's `src/`.
- **Recommendation** marks my own proposals.

---

## 1. `from bpy.types import *`

### 1.1 Runtime

- `bpy.types` is a C module whose classes come from a module-level `__getattr__` that looks the name up in RNA
  (`blender/source/blender/python/intern/bpy_rna.cc:9127-9161`). `__dir__` lists every RNA struct
  (`bpy_rna.cc:9163-9183`).
- Its `__dict__` holds only the internal base types, put there at creation
  (`bpy_rna.cc:9248-9264`): `bpy_struct_meta_idprop`, `bpy_struct`, `bpy_prop`, `bpy_prop_array`,
  `bpy_prop_collection`, `bpy_prop_collection_idprop`, `bpy_func` (their `tp_name`s).
- The module has no `__all__`: `__getattr__("__all__")` finds no struct and falls back to
  `PyObject_GenericGetAttr`, which raises (`bpy_rna.cc:9147-9158`). A star import without `__all__` binds the
  public keys of `__dict__`, not `dir()`, so only those base types are bound.

### 1.2 What ty does with the stubs

- Both stubs define every class at module level in `bpy/types/__init__.pyi` with no `__all__`
  (`stubs-builtin/bpy/types/__init__.pyi`, `stubs-fake/bpy-stubs/types/__init__.pyi`), so ty binds all of them.
- ty limits a star import only through `__all__`: the semantic index adds a definition per exported name
  (`ruff-blender/ty_python_core/src/builder.rs:4203-4244`), each guarded by a `StarImportPlaceholder` predicate,
  and that predicate turns `AlwaysFalse` when the name is not in the exporter's `__all__`
  (`ruff-blender/ty_python_semantic/src/reachability.rs:2020-2036`).

### 1.3 Options

1. **`__all__` in the stubs.** It would work on every type checker. But `__all__` is also the stub's library
   interface: ty's auto-import follows it strictly (`ruff-blender/ty_ide/src/symbols.rs:1261-1270`, used by
   `all_symbols.rs:65`), so `PropertyGroup`, `Operator`, `Panel`, ... would no longer be offered as auto-imports
   from `bpy.types`. Pyright/Pylance read `__all__` the same way. A stub cannot say "public, but not bound by `*`",
   so this trades a rare import form (PEP 8 discourages it) for a regression in the most common editor action. The
   stubs are not wrong about what `bpy.types` *has*; the gap is a runtime quirk of a lazy module.
2. **Checker hook (Recommendation).** A one-line hook in the `StarImportPlaceholder` arm of `reachability.rs`
   makes every name but the base types above unbound when the exporter is Blender's `bpy.types`. The names then
   become unbound in the importer, so `unresolved-reference` is reported exactly as for an `__all__` miss, and
   auto-import is untouched.
3. **Named exception.** Cheap, but the hook costs one upstream line and keeps "every marker passes".

This is a checker rule, not a stub fix, because the stub language cannot express the runtime without breaking
the interface. It is the one place where the rule "stub bugs go to the generators" does not apply.

## 2. `bpy.app.handlers`

- **`persistent`** is a type whose `tp_new` tags the function and returns it unchanged
  (`blender/source/blender/python/intern/bpy_app_handlers.cc:211-247`, `Py_INCREF(value); return value;` at
  `:241-242`). Its docstring says `:type: type` (`bpy_app_handlers.cc:185-187`). No rst `:type:` can say "returns
  its argument", so each generator special-cases it as `def persistent(func: _F, /) -> _F`.
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

**So a one-argument `load_post` handler works.** `check:load` cannot catch a wrong handler shape, because nothing
fires a handler (`scripts/blender/load_feature_addons.py:54-76`).

Where the stub types come from: both generators read the rst that Blender's `doc/python_api/sphinx_doc_gen.py`
writes, which takes the handler types from the C docstrings (`PYDOC_FILEPATH_LOAD_TYPE`, `bpy_app_handlers.cc:41-44`;
`PYDOC_HANDLER_TYPE_NONE`, `:91`). fake-bpy-module then prepends `list of callable[bpy.types.Scene]` to every handler
but `persistent` (`fbm/fake_bpy_module/transformer/bpy_module_tweaker.py:86-99`), a leftover from Blender versions
whose docs had no handler types.

## 3. `bpy_extras.io_utils`

### 3.1 `filepath` and `check_existing`

- **Runtime:** the mixins declare them as Annotated properties in their bodies:
  `ExportHelper.filepath: StringProperty(...)`, `check_existing: BoolProperty(...)`
  (`blender/scripts/modules/bpy_extras/io_utils.py:44-56`), `ImportHelper.filepath: StringProperty(...)`
  (`io_utils.py:119-126`).
- **Why the stubs lacked them:** Blender's `pyclass2sphinx` documents only functions and descriptors from the class
  `__dict__`, and skips every key starting with `_`, so `__annotations__` is never written
  (`blender/doc/python_api/sphinx_doc_gen.py:1916-1976`, filter at `:1938`). Both generators consume that rst.
- **The form decides what operator calls see.** A plain `filepath: str` types the attribute, but it is not a
  property declaration, so an operator-call signature built from the class's properties would not offer
  `filepath=`. The form chosen is `filepath: Annotated[str, StringProperty(...)]`
  ([operator-calls.md](operator-calls.md) section 3).

### 3.2 `invalid-method-override` on `class X(Operator, ImportHelper)`

- `Operator.invoke` returns `set[Literal["RUNNING_MODAL", ...]]` (`stubs-builtin/bpy/types/__init__.pyi:19207`),
  the mixins' `invoke` returned `set[str]` (`stubs-builtin/bpy_extras/io_utils/__init__.pyi:13,17`). `set` is
  invariant, so the first base's method does not override the later one's.
- Source: the docstrings `:rtype: set[str]` at `io_utils.py:72`, `:137` and `:154`. The fix is the operator
  return type there, what the methods really return (`{'RUNNING_MODAL'}`, ...).

### 3.3 `@orientation_helper(...)` loses the class

- Runtime: the decorator adds two annotations and returns the same class (`io_utils.py:190-258`, `return cls`
  at `:256`).
- Its docstring says `:rtype: Callable[[type], type]` (`io_utils.py:200`), so the builtin stub said so. ty applies a
  class decorator's return type to the class name
  (`ruff-blender/ty_python_semantic/src/types/infer/builder/class.rs:324-325`), so the decorated operator becomes
  an instance of `type`. fake-bpy-module's `Callable[typing.Any, typing.Any]` is no valid form, and ty keeps the
  class.
- The stub must be an identity class decorator, `-> Callable[[_C], _C]` with `_C = TypeVar("_C", bound=type)`. The
  rst cannot write a TypeVar, so this is a generator special case like `persistent`.

### 3.4 `axis_forward` / `axis_up`

- Runtime: `orientation_helper` puts `EnumProperty(items=<six axes>, default=..., update=...)` into the
  decorated class's `__annotations__` (`io_utils.py:221-254`). No class body declares them.
- No stub can express this: a decorator that adds attributes would need an intersection type, which Python
  typing does not have. So this one **needs its own checker support**: a third property origin beside Annotated
  and Registered properties, for a class in the MRO decorated with `bpy_extras.io_utils.orientation_helper`. It
  needs the identity decorator of 3.3 first: with `Callable[[type], type]` there is no class left to look up.
- `StaticClassLiteral::decorators` is private
  (`ruff-blender/ty_python_semantic/src/types/class/static_literal.rs:800`) and gives the decorator's result, not
  its callee, so the decorator is read syntactically from the class node.
- Operator calls use the same origin, so `import_file(axis_up="Z")` type-checks.
