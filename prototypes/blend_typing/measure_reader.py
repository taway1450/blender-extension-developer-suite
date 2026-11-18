"""PROTOTYPE, throwaway. Approach A sizing, plus how often code's literal keys are in the file it opens.

Usage: python3 -I measure_reader.py BLENDER_SOURCE_DIR

1. What a reader inside ty needs: the SDNA structs and fields the extractor touches, and where the time goes
   (decompress, block scan, SDNA decode, fact extraction) over the test files the Python tests open by a literal name.
2. The binding a checker would make: for each `tests/python` file that opens one literal `.blend`, how many of its
   literal `bpy.data.<collection>["Name"]` / `.get("Name")` keys name an ID of that type in the file.
"""

import gzip
import os
import re
import statistics
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blendread  # noqa: E402
import extract_manifest  # noqa: E402

touched = Counter()
original_field = blendread.Blend.field


def counting_field(self, struct_name, path):
    touched[(struct_name, path)] += 1
    return original_field(self, struct_name, path)


blendread.Blend.field = counting_field

OPEN = re.compile(r"open_mainfile\(filepath=[^)\n]*?[\"']([\w./-]+\.blend)[\"']")
KEY = re.compile(r"bpy\.data\.(\w+)(?:\[|\.get\()\s*[\"']([^\"']+)[\"']")


def timed_parse(path):
    raw = open(path, "rb").read()
    t0 = time.perf_counter()
    if raw[:4] == b"\x28\xb5\x2f\xfd":
        raw = blendread.zstd_decompress(raw)
    elif raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    t1 = time.perf_counter()
    blend = blendread.Blend(raw)
    t2 = time.perf_counter()
    blend.decode_sdna()
    t3 = time.perf_counter()
    facts = extract_manifest.extract(blend)
    t4 = time.perf_counter()
    return blend, facts, (t1 - t0, t2 - t1, t3 - t2, t4 - t3), len(raw)


def main():
    root = sys.argv[1]
    tests = os.path.join(root, "tests", "python")
    files_dir = os.path.join(root, "tests", "files")
    index = {}
    for dirpath, _, names in os.walk(files_dir):
        for name in names:
            if name.endswith(".blend"):
                index.setdefault(name, os.path.join(dirpath, name))

    timings, sizes = [], []
    keys_total = keys_found = 0
    per_file = []
    collection_of = {coll: code for code, (coll, _) in extract_manifest.ID_CODES.items()}
    for name in sorted(os.listdir(tests)):
        if not name.endswith(".py"):
            continue
        text = open(os.path.join(tests, name), encoding="utf-8", errors="replace").read()
        opened = sorted({os.path.basename(m) for m in OPEN.findall(text)} - {"empty.blend"})
        if not opened:
            continue
        # A test that opens several files: a key counts as found when any of them has it (an upper bound).
        ids, version = {}, 0
        for blend_name in opened:
            path = index.get(blend_name)
            if path is None:
                continue
            try:
                blend, (file_ids, _objects, _materials), t, size = timed_parse(path)
            except Exception as error:  # noqa: BLE001 - a prototype: report and go on
                print(f"  skip {blend_name}: {error!r}")
                continue
            timings.append(t)
            sizes.append(size)
            version = max(version, blend.version)
            for code, names in file_ids.items():
                ids.setdefault(code, []).extend(names)
        if not ids:
            continue
        blend_name = opened[0] + (f" +{len(opened) - 1}" if len(opened) > 1 else "")
        found = total = 0
        for coll, key in KEY.findall(text):
            code = collection_of.get(coll)
            if code is None:
                continue
            total += 1
            found += key in ids.get(code, [])
        keys_total += total
        keys_found += found
        per_file.append((name, blend_name, version, found, total))

    print("== 2. tests that open literal .blend files (not empty.blend), and their literal bpy.data keys")
    for name, blend_name, version, found, total in per_file:
        print(f"  {name:45} {blend_name:40} v{version:<4} keys in file {found}/{total}")
    print(f"  total: {len(per_file)} test files, {keys_found}/{keys_total} literal keys name an ID in the file")

    print("\n== 1a. time per file (ms), median / max, over", len(timings), "files")
    for i, label in enumerate(("decompress", "block scan", "SDNA decode", "facts")):
        col = [x[i] * 1000 for x in timings]
        print(f"  {label:12} {statistics.median(col):7.1f} {max(col):8.1f}")
    print(f"  decompressed size: median {statistics.median(sizes) / 1e6:.1f} MB, max {max(sizes) / 1e6:.1f} MB")

    print("\n== 1b. SDNA struct.field paths the extractor reads (all a Rust reader would need to know by name)")
    for (struct_name, path), count in sorted(touched.items()):
        print(f"  {struct_name}.{path}")


if __name__ == "__main__":
    main()
