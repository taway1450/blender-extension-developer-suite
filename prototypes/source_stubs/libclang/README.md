# libclang source reader

Reads Blender's C/C++ through clang's Python bindings (PyPI `libclang==18.1.1`): a real AST with macros expanded,
every call resolved to its declaration, constant expressions evaluated by clang and every expression typed.

## How

1. **Select** (`parse.py`): a cheap text filter picks the files each area needs (`RNA_def_`, `wmOperatorType *ot`,
   `PyTypeObject`, `CTX_data_equals`, `node_declare`, `bmesh_opdefines.cc`): ~1,290 files, 833 translation units
   (node files are parsed through CMake's unity files; 1,289 units with `--synthesize-flags`).
2. **Flags** (`flags.py`): `--compile-commands PATH` (default `.cache/blender-build/<src>/compile_commands.json`)
   or `--synthesize-flags` (`-x c++ -std=c++20`, `-I` every header directory, feature defines). Generated headers the
   build has not made yet (`RNA_prototypes.hh`) are replaced by a declaration shim: clang drops a whole call that
   names an undeclared `RNA_Object`, so without it context members lose their types.
3. **Lower** (`lower.py`, 2 processes, cached per unit in `.cache/source-stubs/5.2/libclang/cache/`): each function
   body and global initializer becomes a small JSON AST: calls carry the callee's USR (static helpers of the same
   name in two files stay apart), enum constants keep name and value, `sizeof`/`ARRAY_SIZE`/`#define` arithmetic is
   evaluated by `clang_Cursor_Evaluate`, string literals arrive concatenated and macro-expanded, positional
   initializers are mapped to field names through the struct's declaration (not its `/*tp_x*/` comments), and
   expressions carry their C type (`Object *`). makesrna TUs also dump the DNA structs' fields.
4. **Interpret** (`interp.py`): an abstract interpreter runs definition code the way Blender runs it:
   - RNA (`rna.py`): each `RNA_def_<x>(BlenderRNA *)` entry; helpers are followed with the caller's `srna`/`prop`;
     the convenience helpers (`RNA_def_float_vector`, `RNA_def_enum`, `RNA_def_pointer_runtime`,
     `RNA_def_node_enum`) are run from their own bodies in `rna_define.cc` (both its makesrna and runtime compiles),
     so subtype/argument order/defaults come from the source. Only the primitives (`RNA_def_property*`,
     `RNA_def_struct*`, `RNA_def_function*`, `RNA_def_parameter*`) are intrinsics. SDNA inference like makesrna's:
     a float mapped onto `float loc[3]` is an array of 3; a pointer onto `Object *parent` points to `Object`.
   - Operators (`operators.py`): every `X_OT_y(wmOperatorType *ot)`; `WM_operator_properties_*` followed into
     `wm_operator_props.cc`; macro operators via `WM_operatortype_append_macro` / `_macro_define`.
   - Python C API (`pyapi.py`): `PyTypeObject` globals (slots incl. number/sequence/mapping tables), method/getset/
     member tables, and module init functions run so `PyModule_AddObject(mod, "geometry",
     PyInit_mathutils_geometry())` follows into the submodule; `PyStructSequence` types (`bpy.app`) become modules.
   - Context (`context.py`): `*_context(C, member, result)` callbacks (`CTX_data_equals` picks the members of a
     branch), the screen context's `map.add("x", fn)` table, `*_context_dir[]`; types from clang's types
     (`&ob->id` with `ob` an `Object *` -> DNA `Object` -> RNA struct with that `sdna`).
   - Nodes (`nodes.py`): functions calling `node_register_type` (idname from `*_node_type_base`), their `declare`
     run with a symbolic `NodeDeclarationBuilder` (`add_input<decl::Float>` template argument from clang), and
     `node_rna(ntype.rna_ext.srna)`.
   - bmesh (`bmesh.py`): `BMOpDefine` globals, enum/flag slot items from their `BMO_FlagSet` tables; docs from the
     text at AST positions (comments are not in the AST).

Loops run concretely while their condition is known (`for (i = 0; lists[i].name; i++)` defines the 40
`BlendData*` collections, `for (effect = def_effects; effect->struct_name[0]; effect++)` the effect strips);
otherwise, like unknown conditions, both branches / the body run once speculatively (sockets declared there are
marked dynamic). Function pointers held in locals and lambda parameters are followed (`define("GeometryNode",
"GeometryNodeBake", rna_def_geo_bake)`).

## Numbers (5.2, compile_commands)

1,725 RNA structs, 9,980 properties, 3,005 functions; 2,136 operators with 4,967 properties; 255 Python types,
58 modules, 228 module functions; 104 context members (60 typed); 515 node declarations with 2,490 sockets;
82 bmesh operators. Every `bpy.types` class of Blender's builtin stubs is found except the 55 registered from
Python (`*_UL_*`, `*_AST_*`, `*_FH_*`).

## Cannot reach

DNA defaults (`DNA_*_defaults.h`, applied by makesrna through SDNA), items of dynamic enums, definitions in loops
with computed identifiers, anything registered from Python, comments, context members whose pointer flows through
a local variable or a `PointerRNA` path (the Properties editor's members). Facts follow the build configuration
of the flags: `#ifdef WITH_INTERNATIONAL` / `WITH_OPENVDB_BLOSC` branches the compile_commands build disabled are
not seen. See `coverage.md` (`Not reachable`).

## Run

    uv run --no-project --python 3.13 --with libclang==18.1.1 python prototypes/source_stubs/libclang/run.py 5.2 \
        --source .cache/blender-src/5.2-src [--compile-commands PATH | --synthesize-flags] [--jobs 2]

First run parses 833 units (~17 min with 2 processes); later runs reuse the cache (~20 s).
