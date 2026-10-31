"""Type-check the Blender source code of a given version with ty.

Steps:
  1. Create a git worktree of the ``blender`` submodule for the requested version.
  2. Generate bpy stubs with the ``fake-bpy-module`` submodule (needs a matching Blender binary).
  3. Build ty from the ``ty-blender`` submodule.
  4. Run ty on all Python files of the worktree (excluding ``lib/`` and ``extern/``).

Usage:
  uv run scripts/ty_check_blender.py 5.2
  uv run scripts/ty_check_blender.py main --blender "C:/path/to/blender-5.4/blender.exe"

Everything is cached under ``.cache/``; pass ``--force`` to regenerate the worktree and stubs.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BLENDER_SUBMODULE = REPO_ROOT / "blender"
FAKE_BPY_SRC = REPO_ROOT / "fake-bpy-module" / "src"
TY_SUBMODULE = REPO_ROOT / "ty-blender"
CACHE_DIR = REPO_ROOT / ".cache"

EXCLUDED_DIRS = ["lib", "extern"]
# Directories (relative to the Blender source root) that Blender puts on ``sys.path``.
# The generated stubs are searched before these.
BLENDER_SEARCH_PATHS = [
    "scripts/modules",
    "scripts/startup",
    "scripts/addons_core",
    "scripts/freestyle/modules",
]
STUBS_COMPLETE_MARKER = ".complete"


class StepError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(cmd: list[str | Path], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(c) for c in cmd)
    print(f"    $ {printable}", flush=True)
    # Force UTF-8 I/O in Python subprocesses; Windows' legacy code pages can't encode the generated docs.
    env = {**(env or os.environ), "PYTHONUTF8": "1"}
    result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env)
    if result.returncode != 0:
        raise StepError(f"Command failed with exit code {result.returncode}: {printable}")


def git_output(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def resolve_git_ref(version: str, ref_override: str | None) -> str:
    if ref_override:
        return ref_override
    if version == "main":
        return "main"
    return f"blender-v{version}-release"


def ensure_worktree(version: str, ref: str, force: bool) -> Path:
    worktree = CACHE_DIR / "blender-src" / version
    if worktree.exists() and not force:
        log(f"Reusing Blender source worktree {worktree} ({git_output(worktree, 'rev-parse', '--short', 'HEAD')})")
        return worktree

    if worktree.exists():
        log(f"Removing existing worktree {worktree}")
        run(["git", "-C", BLENDER_SUBMODULE, "worktree", "remove", "--force", worktree])
    run(["git", "-C", BLENDER_SUBMODULE, "worktree", "prune"])

    # Prefer the remote-tracking branch, fall back to whatever the ref names (tag, commit, ...).
    candidates = [f"origin/{ref}", ref]
    commit = None
    for _ in range(2):
        for candidate in candidates:
            check = subprocess.run(
                ["git", "-C", str(BLENDER_SUBMODULE), "rev-parse", "--verify", "-q", f"{candidate}^{{commit}}"],
                capture_output=True, text=True,
            )
            if check.returncode == 0:
                commit = check.stdout.strip()
                break
        if commit:
            break
        log(f"Ref {ref!r} not found locally, fetching it from origin")
        run(["git", "-C", BLENDER_SUBMODULE, "fetch", "origin", ref])
        candidates.append("FETCH_HEAD")
    if not commit:
        raise StepError(f"Could not resolve Blender git ref {ref!r}")

    log(f"Creating Blender source worktree for {ref} ({commit[:10]}) at {worktree}")
    worktree.parent.mkdir(parents=True, exist_ok=True)
    # Blender stores test data and some assets in git LFS; we only need the Python sources.
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}
    run(["git", "-C", BLENDER_SUBMODULE, "worktree", "add", "--detach", worktree, commit], env=env)
    return worktree


def blender_binary_version(blender: Path) -> str:
    output = subprocess.run([str(blender), "--version"], capture_output=True, text=True).stdout
    match = re.search(r"^Blender (\d+\.\d+)", output, re.MULTILINE)
    if not match:
        raise StepError(f"Could not determine the version of {blender}:\n{output}")
    return match.group(1)


def find_blender(version: str, explicit: Path | None) -> Path:
    if explicit:
        blender = explicit
        if blender.is_dir():
            blender = blender / ("blender.exe" if sys.platform == "win32" else "blender")
        if not blender.is_file():
            raise StepError(f"Blender binary {blender} does not exist")
    elif version == "main":
        raise StepError("Version 'main' requires an explicit --blender path to a matching Blender build")
    else:
        candidates: list[Path] = []
        if sys.platform == "win32":
            for base in filter(None, [os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")]):
                candidates.append(Path(base) / "Blender Foundation" / f"Blender {version}" / "blender.exe")
        elif sys.platform == "darwin":
            candidates.append(Path("/Applications/Blender.app/Contents/MacOS/Blender"))
        on_path = shutil.which("blender")
        if on_path:
            candidates.append(Path(on_path))
        candidates = list(dict.fromkeys(candidates))

        blender = next((c for c in candidates if c.is_file() and blender_binary_version(c) == version), None)
        if blender is None:
            searched = "\n".join(f"  {c}" for c in candidates) or "  (none)"
            raise StepError(
                f"No Blender {version} binary found. Searched:\n{searched}\nPass --blender <path> explicitly."
            )

    actual = blender_binary_version(blender)
    if version != "main" and actual != version:
        raise StepError(f"{blender} is Blender {actual}, but stubs for Blender {version} were requested")
    log(f"Using Blender {actual} binary {blender}")
    return blender


def run_blender_script(blender: Path, script: Path, *script_args: str | Path) -> None:
    run([blender, "--background", "--factory-startup", "-noaudio", "--python-exit-code", "1",
         "--python", script, "--", *script_args])


def generate_stubs(version: str, source: Path, blender: Path, force: bool) -> Path:
    stubs_dir = CACHE_DIR / "bpy-stubs" / version
    if (stubs_dir / STUBS_COMPLETE_MARKER).exists() and not force:
        log(f"Reusing bpy stubs {stubs_dir}")
        return stubs_dir

    shutil.rmtree(stubs_dir, ignore_errors=True)
    # The rst output is kept until the stubs are complete, so a failed generation can be retried quickly.
    tmp_dir = CACHE_DIR / "bpy-stubs-tmp" / version
    rst_complete = tmp_dir / STUBS_COMPLETE_MARKER
    if rst_complete.exists() and not force:
        log(f"Reusing rst documentation {tmp_dir / 'sphinx-in'}")
    else:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True)
        log("Generating rst documentation with Blender (sphinx_doc_gen.py)")
        run_blender_script(blender, source / "doc" / "python_api" / "sphinx_doc_gen.py", "--output", tmp_dir)
        rst_complete.touch()

    # gen.py always reads generated mod files from this fixed location inside the submodule (gitignored).
    generated_mods = FAKE_BPY_SRC / "mods" / "generated_mods"
    shutil.rmtree(generated_mods, ignore_errors=True)
    generated_mods.mkdir(parents=True)
    gen_modfile = FAKE_BPY_SRC / "gen_modfile"
    try:
        log("Generating fake-bpy-module mod files")
        run_blender_script(blender, gen_modfile / "gen_external_modules_modfile.py",
                           "-m", "addon_utils", "-o", generated_mods / "gen_modules_modfile", "-f", "rst")
        run_blender_script(blender, gen_modfile / "gen_external_modules_modfile.py",
                           "-m", "keyingsets_builtins", "-a", "-o", generated_mods / "gen_startup_modfile", "-f", "rst")
        run_blender_script(blender, gen_modfile / "gen_node_inputs_outputs_for_node_class.py",
                           "-o", generated_mods / "gen_node_inputs_outputs_for_node_class", "-f", "rst")
        bgl_source = next((p for p in (source / "source/blender/python/generic/bgl.cc",
                                       source / "source/blender/python/generic/bgl.c") if p.exists()), None)
        if bgl_source:
            (generated_mods / "gen_bgl_modfile").mkdir()
            run(uv_python_cmd() + [gen_modfile / "gen_bgl_modfile.py", "-i", bgl_source,
                                   "-o", generated_mods / "gen_bgl_modfile" / "bgl.mod.rst", "-f", "rst"])

        log("Generating bpy stubs (fake-bpy-module gen.py)")
        # Same convention as fake-bpy-module's release tooling: the mod version is the Blender version.
        # For 'main' no mod version is passed, which applies all version-ranged mods.
        target_version = "latest" if version == "main" else version
        mod_args = [] if version == "main" else ["-m", version]
        run(uv_python_cmd() + [FAKE_BPY_SRC / "gen.py", "-i", tmp_dir / "sphinx-in", "-o", stubs_dir,
                               "-f", "ruff", "-T", "blender", "-t", target_version, "-l", "warn", *mod_args],
            cwd=FAKE_BPY_SRC)
    finally:
        shutil.rmtree(generated_mods, ignore_errors=True)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    (stubs_dir / STUBS_COMPLETE_MARKER).write_text(f"blender={blender}\nsource={source}\n")
    return stubs_dir


def uv_python_cmd() -> list[str | Path]:
    """Python with fake-bpy-module's requirements installed (in an ephemeral uv environment)."""
    return ["uv", "run", "--no-project", "--python", ">=3.11",
            "--with-requirements", FAKE_BPY_SRC / "requirements.txt", "python"]


def build_ty() -> Path:
    log("Building ty (release)")
    run(["git", "-C", TY_SUBMODULE, "submodule", "update", "--init", "ruff"])
    ruff_dir = TY_SUBMODULE / "ruff"
    run(["cargo", "build", "--release", "--bin", "ty"], cwd=ruff_dir)
    ty = ruff_dir / "target" / "release" / ("ty.exe" if sys.platform == "win32" else "ty")
    if not ty.is_file():
        raise StepError(f"ty binary not found at {ty} after building")
    return ty


def blender_python_version(source: Path) -> str:
    versions_cmake = source / "build_files" / "build_environment" / "cmake" / "versions.cmake"
    match = re.search(r"set\(PYTHON_SHORT_VERSION (\d+\.\d+)\)", versions_cmake.read_text(encoding="utf-8"))
    if not match:
        raise StepError(f"Could not find PYTHON_SHORT_VERSION in {versions_cmake}")
    return match.group(1)


DIAGNOSTIC_RE = re.compile(r"^.+?:\d+:\d+: (?P<severity>\w+)\[(?P<rule>[\w-]+)\]", re.MULTILINE)


def run_ty(ty: Path, version: str, source: Path, stubs: Path) -> Path:
    python_version = blender_python_version(source)
    results = CACHE_DIR / "ty-results" / f"{version}.txt"
    results.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str | Path] = [ty, "check", "--project", source, "--python-version", python_version,
                             "--output-format", "concise", "--no-progress", "--color", "never",
                             "--extra-search-path", stubs]
    for path in BLENDER_SEARCH_PATHS:
        cmd += ["--extra-search-path", source / path]
    for excluded in EXCLUDED_DIRS:
        cmd += ["--exclude", f"{excluded}/"]
    cmd.append(source)

    log(f"Running ty (Python {python_version}) on {source}")
    print(f"    $ {' '.join(str(c) for c in cmd)}", flush=True)
    start = time.monotonic()
    result = subprocess.run([str(c) for c in cmd], cwd=source, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    elapsed = time.monotonic() - start
    results.write_text(result.stdout + result.stderr, encoding="utf-8")

    # ty exits with 1 when it reports diagnostics; anything else non-zero is a failure of ty itself.
    if result.returncode not in (0, 1):
        sys.stderr.write(result.stderr[-5000:])
        raise StepError(f"ty failed with exit code {result.returncode} (full output in {results})")

    counts = collections.Counter((m["severity"], m["rule"]) for m in DIAGNOSTIC_RE.finditer(result.stdout))
    by_severity = collections.Counter()
    for (severity, _), count in counts.items():
        by_severity[severity] += count

    log(f"ty finished in {elapsed:.1f}s: {sum(counts.values())} diagnostics "
        f"({', '.join(f'{n} {s}' for s, n in by_severity.most_common()) or 'none'})")
    if counts:
        width = max(len(rule) for _, rule in counts)
        for (severity, rule), count in counts.most_common():
            print(f"    {count:>7}  {rule:<{width}}  ({severity})")
    log(f"Full output: {results}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", help="Blender version as X.Y (e.g. 5.2), or 'main'")
    parser.add_argument("--ref", help="Blender git ref to check out instead of blender-vX.Y-release / main")
    parser.add_argument("--blender", type=Path, help="Path to a Blender binary (or its directory) matching the version")
    parser.add_argument("--force", action="store_true", help="Recreate the source worktree and regenerate the stubs")
    args = parser.parse_args()

    if args.version != "main" and not re.fullmatch(r"\d+\.\d+", args.version):
        parser.error(f"Version must be X.Y or 'main', got {args.version!r}")

    try:
        blender = find_blender(args.version, args.blender)
        source = ensure_worktree(args.version, resolve_git_ref(args.version, args.ref), args.force)
        stubs = generate_stubs(args.version, source, blender, args.force)
        ty = build_ty()
        run_ty(ty, args.version, source, stubs)
    except StepError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
