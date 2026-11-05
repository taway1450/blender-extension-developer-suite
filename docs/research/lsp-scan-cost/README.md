# Cost of the per-add-on scans in ty's language server

Throwaway findings for the wayfinder ticket "What do the per-add-on scans cost in the language server?"
(taway1450/blender-extension-developer-suite#12). This branch is never merged.

## Setup

- Machine: Windows 11, 2026-11-05.
- Binaries, both built with `cargo build --profile profiling --bin ty`:
  - `ty-stock`: `f076cb67a1`, the prototype's base commit.
  - `ty-proto`: `f2e14916e6` (`prototype/registered-property-use-site` in taway1450/ruff-blender).
    It re-walks the add-on directory with an untracked walk on every failed `bpy.types` lookup. Discovery is a stand-in too.
- Stubs: fake-bpy-module, Blender `main` (`.cache/bpy-stubs/main`), Python 3.13, passed as `extra-paths`.
- Workspaces:
  - `ws_gltf`: a copy of `blender/scripts/addons_core/io_scene_gltf2` (131 `.py` files, legacy `bl_info` add-on) as the only top-level package. No `ty.toml`.
  - `tests/typecheck` with its own `ty.toml`.
- Driver: `lsp_bench.py`, a minimal stdio LSP client. It starts `ty server` (open-files mode, pull diagnostics), runs the scenario below and reads the server's peak working set with psutil. Edits are in memory, as full-text `didChange`.
- 5 runs per binary and workspace, interleaved stock / proto, a fresh server each run. Raw lines are in `results.jsonl`, configs in `cfg_*.json`.

## Scenario

| step | glTF | tests/typecheck |
|---|---|---|
| `first_diag_cold`: open reader 1, pull diagnostics (includes loading the stubs) | `blender/com/gltf2_blender_ui.py` (861 lines, registers and reads ~86 registered properties) | `props_registered/check_props_registered.py` |
| `hover`: a registered-property read in reader 1 | `bpy.data.scenes[0].gltf2_active_variant` | `scene.reg_int` |
| `first_diag_warm`: open reader 2, pull diagnostics | `blender/exp/tree.py` (1153 lines) | `props_registered/ide_props_registered.py` |
| `recheck_noreg`: comment edit in reader 2, pull its diagnostics | | |
| `recheck_reg`: add one `bpy.types.Scene.x = IntProperty()` line in the registrar, pull reader 2's diagnostics | registrar = `gltf2_blender_ui.py` | registrar = `__init__.py` |
| `recheck_reg_registrar`: then pull the registrar's diagnostics | | |
| `recheck_noreg_heavy`: comment edit in reader 1, pull its diagnostics | | |

## Results (median of 5, ms; min–max in brackets)

### glTF exporter

| | stock | proto | delta |
|---|---|---|---|
| first_diag_cold | 356 (331–362) | 509 (464–538) | **+153 (+43 %)** |
| hover | 0.9 | 0.8 | – |
| first_diag_warm (`tree.py`) | 72 | 67 | – |
| recheck_noreg (`tree.py`) | 34 | 29 | – |
| recheck_reg (`tree.py`) | 6.0 | 4.7 | – |
| recheck_reg_registrar (`ui.py`) | 31 (27–33) | 67 (60–71) | **+36 (2.1×)** |
| recheck_noreg_heavy (`ui.py`) | 30 (27–41) | 72 (58–78) | **+42 (2.4×)** |
| peak working set | 129 MB | 132 MB | +3 MB |
| RSS at end | 116 MB | 132 MB | +16 MB |
| diagnostics in `ui.py` / `tree.py` | 174 / 53 | 126 / 53 | 48 false positives gone |

### tests/typecheck

| | stock | proto |
|---|---|---|
| first_diag_cold | 270 | 278 |
| hover | 0.7 | 0.9 |
| first_diag_warm | 2.1 | 2.0 |
| recheck_noreg | 1.6 | 1.5 |
| recheck_reg | 1.2 | 2.4 |
| recheck_reg_registrar | 17 | 16 |
| recheck_noreg_heavy | 5.5 | 7.5 |
| peak working set | 134 MB | 134 MB |

## Reading

- The prototype's cost appears only in a file with many failed `bpy.types` lookups. `gltf2_blender_ui.py` has ≥ 48 such lookups. Each one re-runs discovery and re-walks and re-visits all 131 files, which is about 0.7 ms per lookup. That costs +150 ms on the first check and +35–40 ms on every re-check of that file.
- Files with few failed lookups show no measurable difference: `tree.py` and everything in `tests/typecheck`.
- `tree.py`'s registered-property reads go through `obj.data`, which is not a single `bpy.types` instance there. So its re-check after a registration edit does not depend on the registrar. The registration-edit case is measured on the registrar itself.
- Memory is flat: +3 MB peak.
- Every extra millisecond scales with the *number of lookups*, not the size of the add-on alone. The tracked queries of the plan (ticket #8) compute the per-add-on map once per revision and turn each lookup into a map read. That removes the multiplier by construction.
- A "no `bpy.props` import" pre-filter would not have helped this worst case at all, because glTF imports `bpy.props`.
