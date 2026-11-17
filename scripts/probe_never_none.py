# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Probe which RNA pointers and function returns Blender leaves None, for ticket #109 (research only).

Steps:
  1. Run Blender (background, factory startup) with ``scripts/blender/probe_never_none.py synthetic``: edge states
     built in factory startup (new data, copies, save and append, invalid arguments, every node tree and ID type,
     ``read_homefile`` / ``read_factory_settings`` with and without ``use_empty``).
  2. Run it with ``files`` over every .blend under the source worktree's ``tests/files`` (old versions back to
     1.62 included; ``invalid_blendfiles/`` left out). A file that crashes Blender is recorded and skipped on the
     next run.
  3. Write ``.cache/never-none-probe/<version>/table.md``: per member and state, how many reads were None.

Usage:
  uv run scripts/probe_never_none.py main
  uv run scripts/probe_never_none.py main --limit 50     # only the first 50 corpus files
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
from pathlib import Path

from _common import CACHE_DIR, REPO_ROOT, log, main_wrapper, validate_version
from generate_stubs import find_blender, worktree_path

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_never_none.py"
MAX_CRASHES = 200


def blender_cmd(blender: Path, *args: str | Path) -> list[str]:
    return [
        str(blender),
        "--background",
        "--factory-startup",
        "-noaudio",
        "--python-exit-code",
        "1",
        "--python",
        str(PROBE),
        "--",
        *map(str, args),
    ]


def corpus(source: Path, limit: int | None) -> list[str]:
    root = source / "tests" / "files"
    paths = sorted(
        str(p)
        for p in root.rglob("*.blend")
        if "invalid_blendfiles" not in p.parts and p.stat().st_size > 1024
    )
    return paths[:limit] if limit else paths


def run_files(blender: Path, out: Path, paths: list[str]) -> list[str]:
    file_list, results, skip = out / "files.txt", out / "files.jsonl", out / "crashed.txt"
    file_list.write_text("\n".join(paths), encoding="utf-8")
    crashed = skip.read_text(encoding="utf-8").split() if skip.exists() else []
    for _ in range(MAX_CRASHES):
        proc = subprocess.run(blender_cmd(blender, "files", results, file_list, skip), capture_output=True, text=True)
        current = Path(str(results) + ".current")
        if not current.exists():
            if proc.returncode:
                log(f"Probe run failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
            break
        bad = current.read_text(encoding="utf-8").strip()
        log(f"Blender crashed on {bad}, skipping it")
        crashed.append(bad)
        skip.write_text("\n".join(crashed), encoding="utf-8")
        current.unlink()
    return crashed


def table(synthetic: list[dict], files: list[dict]) -> str:
    rows = [(r["member"], r["state"], r["none"], r["total"], r["note"], "") for r in synthetic]
    per_file = collections.defaultdict(lambda: [0, 0, set()])
    for entry in files:
        for r in entry["records"]:
            key = (r["member"], r["state"].split(" (saved by")[0].replace("loaded file", "corpus files"))
            per_file[key][0] += r["none"]
            per_file[key][1] += r["total"]
            if r["none"]:
                per_file[key][2].add(Path(entry["file"]).name)
    for (member, state), (none, total, examples) in sorted(per_file.items()):
        rows.append((member, state, none, total, "", ", ".join(sorted(examples)[:5])))
    lines = ["| Member | State | None | Reads | Note | Files with None |", "|---|---|---|---|---|---|"]
    for member, state, none, total, note, examples in sorted(rows, key=lambda r: r[0]):
        note = note.replace("|", "\\|")
        lines.append(f"| `{member}` | {state} | {none} | {total} | {note} | {examples} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_version, help="Blender version (X.Y) or build name (e.g. main)")
    parser.add_argument("--blender", type=Path, help="Blender binary (or its directory) to use")
    parser.add_argument("--limit", type=int, help="Only probe the first N corpus files")
    args = parser.parse_args()

    blender = find_blender(args.version, args.blender)
    out = CACHE_DIR / "never-none-probe" / args.version
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)

    log("Probing the synthetic edge states")
    proc = subprocess.run(blender_cmd(blender, "synthetic", out / "synthetic.json", work), capture_output=True, text=True)
    if proc.returncode:
        log(f"Synthetic probe failed:\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
    synthetic = json.loads((out / "synthetic.json").read_text(encoding="utf-8"))

    paths = corpus(worktree_path(args.version), args.limit)
    log(f"Probing {len(paths)} .blend files")
    crashed = run_files(blender, out, paths)
    results = out / "files.jsonl"
    files = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()] if results.exists() else []
    errors = [f for f in files if f["error"]]

    text = table(synthetic, [f for f in files if not f["error"]])
    text += f"\n{len(files) - len(errors)} files probed, {len(errors)} failed to open, {len(crashed)} crashed Blender.\n"
    (out / "table.md").write_text(text, encoding="utf-8")
    log(f"Wrote {out / 'table.md'}")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
