# regex: Blender's C/C++ source read with plain Python

This prototype reads Blender's source with the Python standard library only. It uses no compiler, no libclang and no
build. The output goes through the shared contract in `../common/`: facts JSON, `.pyi` stubs and `coverage.md`.
Facts the contract has no field for go to `extra.json`.

## Run

```sh
uv run --no-project --python 3.13 python prototypes/source_stubs/regex/run.py 5.2 --source .cache/blender-src/5.2-src
# one or more areas only, without the Python scripts:
uv run --no-project --python 3.13 python prototypes/source_stubs/regex/run.py 5.2 --source ... --areas rna,context --no-python
```

The output lands in `.cache/source-stubs/5.2/regex/`. A full run takes about a minute on one process.
`compare_ref.py [version] [module ...]` measures the stubs against `.cache/bpy-stubs-builtin/<version>`.

## How it reads

The source passes through a few small layers:

- `ctok.py`
  - Strips comments (line numbers kept), tokenizes and joins string literals.
  - Runs a preprocessor-lite: `#if`/`#ifdef`/`#elif` are evaluated with an assumption table (`RNA_RUNTIME` off for
    makesrna, `WITH_*` on, Linux), `#define` macros are collected and `#include` is resolved through a header index.
  - Splits the top level into functions, variables, enums and structs (namespaces and `extern "C"` are transparent,
    and a macro call without a semicolon ends a declaration).
  - Evaluates constants: numbers, enums, `#define`s and casts.
- `macro.py`: object-like and function-like macros, `#`, `##` and `__VA_ARGS__`.
- `interp.py`: a small symbolic executor for definition code.
  - It runs blocks, `if`/`switch` (known values pick the branch, unknown ones run both), loops (unrolled when bounds
    are known), lambdas, function pointers and brace-initialized struct arrays.
  - It follows the source's own helper functions with the caller's arguments bound.
  - Calls it cannot follow become warnings, not errors.
- `rnadef.py`: the `RNA_def_*` API.
  - Each helper's type, subtype and flags are read from `RNA_define.hh` and the bodies in `rna_define.cc`.
  - Units come from `RNA_types.hh`.
  - Array lengths and string sizes come from the DNA members named by `RNA_def_property_sdna` (`dna.py`), as makesrna
    does.

## Areas

| Area | Source | Method |
|---|---|---|
| RNA | `makesrna/intern/rna_*.cc` | Runs `RNA_def_*` functions, the `PROCESS_ITEMS` list order, shared and local enum arrays, DNA-sized arrays and makesrna's automatic pointer types. |
| Operators | every `.cc` with `wmOperatorType` | Runs each `*_OT_*` function with `ot` bound. Covers callbacks, flags, properties including those added by shared helpers (constants select their branches), and macro operators. |
| Nodes | `source/blender/nodes/**` | Runs the registration functions (`*_node_type_base`): UI name and description, runtime RNA through `node_rna`/`RNA_def_node_*`. Also reads socket chains in `node_declare` and its helpers. |
| Python C API | `source/blender/python`, freestyle, audaspace | Reads `PyTypeObject` positionally or by designator, plus runtime `tp_*` assignments, slot tables, method/getset/member tables, `PyModuleDef`, module adds, struct sequences, `PyDoc_STRVAR` docstrings via `rstdoc.parse_directive`, and the `_keywords`/format of each argument parser. |
| Context | editors' `*_context` callbacks and `screen_context.cc` | Reads `CTX_data_equals` regions, `map.add` registries and `*_context_dir` tables. A type comes from `&RNA_X`, from the C type of the ID variable (declarations, range-for, macro-declared variables, DNA member chains mapped to RNA by `sdna`), or from `GS(id->name) == ID_XX` checks. Helpers that receive `result` are followed. |
| bmesh | `bmesh_opdefines.cc` | Reads `BMOpDefine` tables for slot types and subtypes, enum items, and the raw comments above each operator and slot. |

## What it cannot reach

- **Values computed at run time.** These are counted in `coverage.warnings`:
  - identifiers built with `BLI_snprintf` from runtime data;
  - socket lists built from node storage (zones, bundles, menus);
  - properties added in `invoke`.
- **Behaviour behind unknown conditions.** Both branches are kept, so the union is reported.
- **Defaults from `DNA_*_defaults.h`.** They are not read.
- **Callbacks behind data structures.** An RNA `itemf` result, a `typef` refinement or a context member whose name is
  not a literal is out of reach.
- **The Python package layout.** `freestyle.types` re-exports `_freestyle`, and `bpy.utils` is mostly Python. These
  come from the shared ast reader (`--python`), not from C.
