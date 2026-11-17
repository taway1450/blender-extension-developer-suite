# Spec #123 C1: the Blender-fix group, the check setup and the accepted leftovers

C1 (#124) sorts the diagnostics that `check:blender main` misfiled as Blender fixes, cleans up the check
setup, and says why four causes of right code stay in the report. Counts are `check:blender main` at Blender
`e8e03296af`, before (`5db191c`) and after this change; "done area" is shipped code, presets, examples and
templates.

## Totals

| stub set | errors before | errors after | move | `blender-fix` before | after | unsorted in the done area |
|---|---:|---:|---:|---:|---:|---:|
| Blender's own (builtin) | 7,125 | 7,031 | −94 | 74 | 5 | 0 |
| fake-bpy-module | 9,593 | 9,466 | −127 | 463 | 5 | 0 |

The error moves come from the check setup alone; regrouping moves diagnostics between causes, not in or out.

## The Blender-fix group

What stays is a real bug, all of it in tools outside the done area (both stub sets):

| site | cause | bug |
|---|---|---|
| `release/datafiles/blender_icons_geom.py:133` | `undefined-name` | `me_loops_color_active` is never bound (`NameError` for a mesh with an active color) |
| `tools/utils_ide/qtcreator/externaltools/qtc_assembler_preview.py:59`, `:76` | `undefined-name` | `time` is never imported |
| `source/blender/python/rna_dump.py:115` | `undefined-name` | `bpy` is never imported (works only when pasted into Blender's console) |
| `release/lts/create_release_notes.py:22` | `return-annotation` | `main() -> int` returns nothing |

### What left it (69 builtin, 458 fake-bpy-module)

| from | to | builtin | fake-bpy-module | why |
|---|---|---:|---:|---|
| `undefined-name` | `reload-idiom` | 4 | 4 | `bl_ui/__init__.py` imports its submodules with `__import__(fromlist=_modules)`; `_icon_cache` sits under `if "_icon_cache" in locals():` |
| `undefined-name` | `runtime-name` (new, typing debt) | 34 | 34 | names put into `globals()` from a parsed C header (`rst_from_bmesh_opdefines.py`, 25) or given by GDB (`gdb_struct_repr_c99.py`, 9) |
| `none-for-non-optional` | `stub-none-mismatch` (new, typechecker fix) | 7 | 2 | `Area.header_text_set(None)` (5) and `GPUVertBuf.attr_fill(id=…)` after `attr_add` (2): the stubs disagree with the C API; fixed by the Blender spec |
| `none-for-non-optional`, `return-annotation` | `untyped-python` | 18 | 21 | Rigify's `IdPropSequence` / `TypedObject` / lazy returns, Freestyle's `zip(stroke, <generator typed None>)`, glTF's `Keyframe(None, …)` |
| `return-annotation` | `python-optional` | 2 | 2 | Rigify's `get_rigify_target_rig` and glTF's `Keyframe.value`: a plain Optional in an untyped package |
| `return-annotation` | `general-typing` | 1 | 1 | `hash_service.py`: `-> hashlib._Hash`, a private typeshed name |
| `missing-argument` | `general-typing` | 2 | 2 | `install_linux_packages.py`: the base method's every override defaults `version` |
| `none-for-non-optional` | `general-typing` | 1 | 1 | `gdb.set_convenience_variable(name, None)`: GDB takes None, its stub does not |
| `missing-argument`, `tooldef` | `fake-bpy-python-module` | – | 364 | fake-bpy-module drops `ToolDef.from_fn`'s `@staticmethod` |
| `none-for-non-optional`, `return-annotation` | `fake-bpy-python-module` | – | 22 | values of Blender's Python modules that fake-bpy-module's stubs type `-> None` (`keyingsets_utils`, `_bpy_internal`, `bpy.utils.app_template_paths`, `_rna_info`) |
| `unchecked-pointer-bug` | `object-data-untagged` | – | 5 | `cam.data.shift_x = 0` in the VR camera operator: fake-bpy-module's untagged `Object.data` union, not the pointer bug listed for that class |

## The check setup

| change | builtin errors | fake-bpy-module errors | in the done area (builtin) |
|---|---:|---:|---:|
| link more of Blender's bundled packages (`setuptools`, `requests`, `urllib3`, `certifi`, `cattrs`, `docutils`, `zstandard`, `OpenImageIO`, `opentimelineio`) beside numpy | −35 | −35 | −10 |
| search paths Blender's tools and tests add themselves (`tools/modules`, `tools/utils_maintenance/modules`, `bl_pkg/tests/modules`) | −14 | −14 | −5 |
| `allowed-unresolved-imports` for modules nothing can resolve: compiled into Blender (`aud`, `_bpy_path`, `_cycles`), bundled compiled without stubs (`pxr`, `PyOpenColorIO`, `MaterialX`, `oslquery`, `openvdb`, `OpenEXR`), GDB's `gdb`, and developer-tool requirements Blender does not bundle (`pygments`, `clang`, `sphinx`, `scipy`, ...) | −52 | −85 | −12 |
| new diagnostics in code that now has real types (`_bpy_internal/http/downloader.py` reading `requests` responses, 4; tools, 3; and 4 unused `type: ignore` warnings) | +7 | +7 | +4 |

`pxr`, `PyOpenColorIO`, `MaterialX` and `oslquery` were tried as links first: their packages are thin wrappers
around extension modules without stubs, which gave 418 false `has no member` errors (mostly the USD tests). A
stale link of a package that leaves the list is now removed.

What `unresolved-import` keeps (builtin 41, 31 shipped) are real gaps: Blender's generated stubs shadow
`bpy_extras` and `freestyle` and lack modules and members their source has (`bpy_extras.node_shader_utils`,
`wm_utils`, `bmesh_utils`, `freestyle.utils.BoundedProperty`), script-mode fallback imports
(`_bl_i18n_utils`, `io_scene_fbx/encode_bin.py`), and CPython's `_sha1` / `_sha2` / `_md5`.

**Not changed by the setup:** the reload idiom (25) and the private members (12). No check setting reaches
them without hiding real errors in the same files: ty's only per-file lever is a rule's level. The reload
idiom needs the ty fork's reload guard to cover a package's submodules imported inside functions (Cycles,
the importers), the `if "x" not in locals(): … else: reload` form (Pose Library) and modules in no add-on
(`bl_ui`, `bl_operators`). The private members (`bpy.app.handlers._extension_repos_*`,
`bpy.utils._sys_path_ensure_append`) are left out of the generated stubs, which is stub-generator work.

## Accepted leftovers

Right code ty cannot prove, kept as typing debt with no rule: each is a context member that exists whenever
the code can run, but no check, poll or Blender callback contract shows it. Builtin counts (done area / total).

| cause | done area | total | stays because |
|---|---:|---:|---|
| `editor-context-member` | 50 | 50 | An operator's `invoke` / `modal` (or a gizmo's `exit`) runs only interactively, in the editor that started it, so `context.area`, `space_data`, `region` and `window` exist. The same holds for the helpers and draw handlers those operators install (Node Wrangler's `draw_rounded_node_border`) and an exporter's file-browser panel. An Assumption rule would need the call graph from `invoke` to its helpers. |
| `script-context-member` | 47 | 47 | Doc examples and text-editor templates document the context they run in: "with an active object, `bpy.context.object.data` …". Making them check would teach readers a check the example is not about. |
| `window-context-in-execute` | 25 | 59 | An operator's `execute`, and the importer and exporter code it calls, reads `context.window`, `screen`, `space_data`, `workspace` or `collection`. They are None only in a background or `temp_override` call that leaves them out, which these operators' callers never make. The 34 outside the done area are tests that run with a window. |
| `rarely-none-member` | 13 | 18 | None only in states the code cannot run in: the active view layer's `depsgraph` while an operator runs, the add-on key configuration once Blender started, a property callback's context, the camera of a scene Freestyle renders, an asset's `asset_data` in the asset browser. |

With fake-bpy-module the same four count 58 / 51 / 59 / 18 (done area 58 / 51 / 25 / 13).
