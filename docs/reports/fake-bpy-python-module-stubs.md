# fake-bpy-module's stubs of Blender's Python modules (#141)

fake-bpy-module stubbed Blender's Python modules (`addon_utils`, `bl_ui`, `bl_operators`, `_bpy_internal`,
`bpy_extras.node_shader_utils`, ...) with `inspect`, in `src/gen_modfile/gen_external_modules_modfile.py`, and
passed what it saw through its API-docs pipeline as mod files. The stubs lost `__init__` and the other dunders,
instance and dataclass fields, module constants, private functions, annotations (every return `-> None`),
builtin bases and `@contextmanager`. Spec #140 asked to try two routes on a few modules and pick one.

All counts are `check:blender main --generator fake-bpy-module`, done area (shipped, presets, examples,
templates), Blender `38d1df8a1b`.

## The prototypes

Both routes were tried on the same three modules, which cover the lossy shapes:

- `_bpy_internal.assets.remote_library.blender_asset_library_openapi`: dataclasses;
- `bl_ui.space_toolsystem_common`: a `NamedTuple` built with `namedtuple()`, static methods;
- `addon_utils`: private functions and module constants.

| route | `fake-bpy-python-module` | errors (all areas) |
|---|---:|---:|
| before | 637 | 7718 |
| A: patch `gen_external_modules_modfile.py` | 532 (−105) | 7452 |
| B: stubs from the Python source | 166 (−471) | 6987 |

**Route A** kept `__init__` / `__enter__` / `__exit__`, class annotations (dataclass fields), private functions,
module constants (typed by their value) and parameter and return annotations, written as `:type:` / `:rtype:`
into the mod files. What it cannot reach:

- instance attributes (`self.x = ...` in `__init__`): `inspect` sees only class members;
- a class built at runtime (`ToolDef = namedtuple(...)` with methods attached), so `ToolDef.from_fn` stays an
  instance method;
- `@contextmanager`: the function inspect sees is the wrapped generator;
- every annotation goes through the docs pipeline's type parser, which knows a fixed set of spellings;
- the docs pipeline breaks on Python signatures it never met: `def f(*_, *, x)` came out with two `*`, once in
  the mod writer and once in the pipeline's own code writer. Each such case is a fix in two places.

**Route B** writes each module's stub from its source with `ast`: the function bodies go, and everything else
the source declares stays as written (imports, assignments, `if` / `try` blocks, classes with bases and
decorators, annotations, defaults, docstrings). Instance attributes assigned on `self` in a method are declared
on the class (typed by an annotation, a literal or an annotated parameter, else `typing.Any`). It needs no
type parser and no knowledge of the docs format.

**Decision: route B.** It is the more faithful by a wide margin, and it is cheaper to keep: about 350 lines
of `ast` code with unit tests, outside the docs pipeline, where route A needs a new case for every shape the
source can take.

## The implementation

On fake-bpy-module's `stub-generator` branch:

- `gen_external_modules_modfile.py` also writes `source_modules.json`, each module's source file.
- `gen.py` writes those modules' stubs from the source (`fake_bpy_module/source_stub.py`) over the ones the
  docs pipeline made from the mod files. The mod files still go through the pipeline, so `bpy.types`' aliases
  to registered classes (spec slice P2) and every reference to these classes keep working.
- Modules the API docs document (`.. module::` in the RST: `bpy.utils`, `bpy_extras.io_utils`, `gpu_extras`,
  ...), `bpy` and `_bpy_types` keep their stubs from the docs. Undocumented modules under them
  (`bpy_extras.node_shader_utils`, `bpy_extras.wm_utils.progress_report`, `bpy.utils.toolsystem`) are written
  from the source.
- The docs pipeline's type parser now knows `Iterator[...]`. Documented `:rtype: Iterator[str]`
  (`bpy.utils.app_template_paths`, the Freestyle generators) had become `None`.

Unit tests: `tests/python/fake_bpy_module_test` (`SourceStubTest`, `WriteStubsTest`, and a `DataTypeRefinerTest`
case for `Iterator`), 126 tests passing.

## The move

| cause (done area) | before | after |
|---|---:|---:|
| `fake-bpy-python-module` | 637 | 1 |
| `fake-bpy-type-alias` | 11 | 3 |
| errors (all areas) | 7718 | 6220 |
| `unsorted` (done area) | 0 | 0 |

The report of #114 counted 234 `fake-bpy-python-module` sites; the slices of spec #132 sorted 403 more into it
before this one.

What the stubs now say makes some diagnostics appear that Blender's own stubs also give: a function that
returned `-> None` returns its real type, so the narrowing and pointer causes of the code that reads it count
more (`narrowed-by-menu-prefix` 87 → 100, `ui-draw-pointer` +4, `object-data-untagged` +2). The
`narrowed-by-menu-prefix` sites all match a builtin site.

A registered class's method read through `bpy.types` (`bpy.types.PREFERENCES_OT_addon_install._target_path_items`)
now shows as a bound method; `_buckets.py` sorts it under `fake-bpy-type-alias` (slice P2).

`check:features` with fake-bpy-module: the four Freestyle generator markers of `api_stub_gaps` now pass (the
`Iterator[...]` part of the named exception of spec #132). `check:ide` is unchanged.

## What stays

- `doc/python_api/examples/aud.0.py:12`, `aud.Sound('music.ogg')`: `aud` is a C module. Its RST gives the
  constructor as the class signature (`.. class:: Sound(filename, stream=0)`), which fake-bpy-module's docs
  pipeline does not turn into `__init__`. It is not a Python-module stub. The `object.__init__` pattern sorts
  it here; it belongs with the C types of slice P4 (Blender's own stubs have no `aud` at all).
- Unannotated functions return `Unknown` in a stub, where ty infers a return type from the source. Diagnostics
  that need the inferred type are fewer with fake-bpy-module than with Blender's own stubs, which resolve these
  modules to the source. This loses no diagnostic the `inspect` stubs gave.
- A dataclass or `NamedTuple` gets no attributes from its methods (they would become fields).
