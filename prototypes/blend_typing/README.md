# PROTOTYPE: typing code from a .blend file (throwaway)

Throwaway code that answers one question from `docs/research/blend-file-typing.md`: what types can a checker get from
a `.blend` without running Blender, and how would they reach a script? The answers are in §8 of that note. Nothing here
is production code, and nothing else in the repo depends on it.

| File | Approach | What it shows |
|---|---|---|
| `blendread.py` | shared | a dependency-free reader: header, blocks, SDNA, zstd (system libzstd) and gzip |
| `extract_manifest.py` | B | `.blend` → TOML manifest (IDs, object and data types, modifiers, material nodes and sockets) |
| `usd_materials_export.blend-manifest.toml` | B | its output for `tests/files/usd/usd_materials_export.blend` |
| `gen_stubs.py` | C | manifest → overlay `.pyi` with `Literal` keys |
| `addon/` | C | an add-on that reads `bpy.data` and the overlay side by side with `reveal_type` |
| `measure_reader.py`, `measure_reader.out` | A | the SDNA fields a reader needs, time per stage, and how many test keys the files hold |

Run (files under `.cache/blender-src/main` have their LFS content; those under `blender/` are pointers):

```bash
python3 -I prototypes/blend_typing/extract_manifest.py .cache/blender-src/main/tests/files/usd/usd_materials_export.blend > /tmp/m.toml
```

```bash
python3 -I prototypes/blend_typing/gen_stubs.py /tmp/m.toml > prototypes/blend_typing/addon/_blend/usd_materials_export.pyi
```

```bash
cp -r prototypes/blend_typing/addon examples/addons/prototype_blend_typing && mise run check:addons main prototype_blend_typing; rm -rf examples/addons/prototype_blend_typing
```

```bash
python3 -I prototypes/blend_typing/measure_reader.py .cache/blender-src/main
```
