# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Generate bpy stubs for a Blender version with ``fake-bpy-module``, Blender's own stub generator or the runtime one.

The stub generators:
  fake-bpy-module  the ``fake-bpy-module`` submodule, from the rst API docs Blender generates; stubs in
                   ``.cache/bpy-stubs/<version>``
  builtin          Blender's ``doc/python_api/sphinx_stub_gen.py`` (Blender 5.2 and later), from the same rst docs;
                   stubs in ``.cache/bpy-stubs-builtin/<version>``
  runtime          the fork's ``doc/python_api/runtime_stub_gen.py``, in a running Blender: the builtin stubs of
                   that Blender with its default add-ons disabled, plus what only the runtime has (startup classes
                   with their members, the Python source of the script folders); stubs in
                   ``.cache/bpy-stubs-runtime/<version>``, its rst and facts in
                   ``.cache/bpy-stubs-runtime-work/<version>``. ``all`` leaves it out.

Steps:
  1. Create a git worktree of the ``blender`` submodule for the requested version
     (``sphinx_doc_gen.py`` and the bgl sources are taken from it).
  2. Download the matching official Blender binary into ``.cache/blender-bin/`` unless it is
     already there (or ``--blender`` is passed). Versions other than X.Y (e.g. ``main``) name a
     Blender build from source, made with ``build_blender.py`` into the same directory.
  3. Run Blender to generate the rst API docs (cached in ``.cache/bpy-rst/<version>``).
  4. fake-bpy-module: run Blender to generate fake-bpy-module's mod files, then fake-bpy-module's
     ``gen.py`` to turn the rst docs into stubs.
     builtin: run ``sphinx_stub_gen.py`` of the source worktree on the rst docs.
     runtime: instead of steps 3 and 4, run ``runtime_stub_gen.py`` of the source worktree in Blender, which writes
     and parses its own rst (with ``docutils`` installed into ``.cache/runtime-stubs-site``).

Usage:
  uv run scripts/generate_stubs.py 5.2                       # both generators (builtin where available)
  uv run scripts/generate_stubs.py 5.2 --generator builtin
  uv run scripts/generate_stubs.py main          # after: uv run scripts/build_blender.py main
  uv run scripts/generate_stubs.py main --blender "C:/path/to/blender-5.4/blender.exe"

Everything is cached under ``.cache/``; pass ``--force`` to regenerate the worktree and stubs.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

from _common import (
    BLENDER_SUBMODULE,
    CACHE_DIR,
    COMPLETE_MARKER,
    FAKE_BPY_MODULE,
    FAKE_BPY_SRC,
    StepError,
    blender_script_command,
    exe,
    git_output,
    is_release,
    log,
    main_wrapper,
    run,
    validate_version,
)
from download_blender import BUILD_INFO, cached_blender, download_blender

FAKE_BPY, BUILTIN, RUNTIME, ALL = "fake-bpy-module", "builtin", "runtime", "all"
GENERATORS = (FAKE_BPY, BUILTIN, RUNTIME)
STUBS_DIRS = {
    FAKE_BPY: CACHE_DIR / "bpy-stubs",
    BUILTIN: CACHE_DIR / "bpy-stubs-builtin",
    RUNTIME: CACHE_DIR / "bpy-stubs-runtime",
}
RST_DIR = CACHE_DIR / "bpy-rst"
PYTHON_API_DIR = Path("doc") / "python_api"
BUILTIN_STUB_GEN = PYTHON_API_DIR / "sphinx_stub_gen.py"
RUNTIME_STUB_GEN = PYTHON_API_DIR / "runtime_stub_gen.py"
RNA_INFO_MODULE = Path("scripts") / "modules" / "_rna_info.py"
RUNTIME_WORK_DIR = CACHE_DIR / "bpy-stubs-runtime-work"
# $BLENDER_USER_RESOURCES of the runtime generator: preferences without add-ons, per version.
RUNTIME_USER_DIR = CACHE_DIR / "bpy-stubs-runtime-user"
# docutils for the runtime generator, which parses rst in Blender's Python.
RUNTIME_SITE_DIR = CACHE_DIR / "runtime-stubs-site"
# Pinned, so that a fresh cache parses the rst as the recorded baselines did.
RUNTIME_SITE_REQUIREMENT = "docutils==0.23"


def resolve_git_ref(version: str, ref_override: str | None) -> str:
    if ref_override:
        return ref_override
    if not is_release(version):
        return version
    return f"blender-v{version}-release"


def resolve_commit(ref: str, fetch: bool = False) -> str:
    """Return the commit ``ref`` names in the blender submodule, fetching it from origin if it is
    not known locally (or always with ``fetch``)."""

    def lookup(candidate: str) -> str | None:
        check = subprocess.run(
            ["git", "-C", str(BLENDER_SUBMODULE), "rev-parse", "--verify", "-q", f"{candidate}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        return check.stdout.strip() if check.returncode == 0 else None

    if not fetch:
        # Prefer the remote-tracking branch, fall back to whatever the ref names (tag, commit, ...).
        for candidate in (f"origin/{ref}", ref):
            if commit := lookup(candidate):
                return commit
        log(f"Ref {ref!r} not found locally, fetching it from origin")
    run(["git", "-C", BLENDER_SUBMODULE, "fetch", "origin", ref])
    if commit := lookup("FETCH_HEAD"):
        return commit
    raise StepError(f"Could not resolve Blender git ref {ref!r}")


def worktree_path(version: str) -> Path:
    return CACHE_DIR / "blender-src" / version


def worktree_commit(version: str) -> str | None:
    """HEAD of the source worktree for ``version``, or None if it is missing or no longer a git worktree."""
    worktree = worktree_path(version)
    if not worktree.exists():
        return None
    check = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"], capture_output=True, text=True)
    return check.stdout.strip() if check.returncode == 0 else None


def ensure_worktree(version: str, ref: str | None = None, force: bool = False, update: bool = False) -> Path:
    """Return a git worktree of the Blender source for ``version``, creating it if needed.

    With ``update`` the ref is fetched again and an existing worktree is moved to its latest commit.
    """
    ref_override = ref
    ref = resolve_git_ref(version, ref)
    worktree = worktree_path(version)
    # Blender stores test data and some assets in git LFS; we only need the Python sources.
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}
    head = worktree_commit(version)
    if head and not force:
        # An explicit ref moves the worktree too: otherwise `--ref other` would silently build the old checkout.
        if (update or ref_override) and (commit := resolve_commit(ref, fetch=update)) != head:
            log(f"Updating Blender source worktree {worktree} to {ref} ({head[:10]} -> {commit[:10]})")
            run(["git", "-C", worktree, "checkout", "--detach", commit], env=env)
            return worktree
        log(f"Reusing Blender source worktree {worktree} ({head[:10]})")
        return worktree

    if head:
        log(f"Removing existing worktree {worktree}")
        run(["git", "-C", BLENDER_SUBMODULE, "worktree", "remove", "--force", worktree])
    elif worktree.exists():
        # E.g. its metadata in the submodule's .git/worktrees/ is gone; git can't remove it then.
        log(f"Removing {worktree}, which is no longer a git worktree")
        shutil.rmtree(worktree)
    run(["git", "-C", BLENDER_SUBMODULE, "worktree", "prune"])

    commit = resolve_commit(ref, fetch=update)
    log(f"Creating Blender source worktree for {ref} ({commit[:10]}) at {worktree}")
    worktree.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "-C", BLENDER_SUBMODULE, "worktree", "add", "--detach", worktree, commit], env=env)
    return worktree


VERSIONS_CMAKE = "build_files/build_environment/cmake/versions.cmake"  # in the Blender source


def python_short_version(versions_cmake: str) -> str:
    """Blender's Python, X.Y, from the text of its ``versions.cmake``."""
    match = re.search(r"set\(PYTHON_SHORT_VERSION (\d+\.\d+)\)", versions_cmake)
    if not match:
        raise StepError(f"Could not find PYTHON_SHORT_VERSION in {VERSIONS_CMAKE}")
    return match.group(1)


def blender_python_version(source: Path) -> str:
    return python_short_version((source / VERSIONS_CMAKE).read_text(encoding="utf-8"))


def blender_version_output(blender: Path) -> str:
    return subprocess.run([str(blender), "--version"], capture_output=True, text=True).stdout


def blender_binary_version(blender: Path) -> str:
    output = blender_version_output(blender)
    match = re.search(r"^Blender (\d+\.\d+)", output, re.MULTILINE)
    if not match:
        raise StepError(f"Could not determine the version of {blender}:\n{output}")
    return match.group(1)


def blender_fingerprint(blender: Path) -> str:
    """One line naming the Blender build ``blender`` is, so caches made with it can tell a rebuild: a source build's
    ``.build-info`` (commit, preset, configure hash; next to the binary, or above the macOS app bundle), a release's
    version and build lines from ``--version``."""
    for directory in list(blender.parents)[:4]:
        if (build_info := directory / BUILD_INFO).is_file():
            return ",".join(filter(None, build_info.read_text().splitlines()))
    lines = [line.strip() for line in blender_version_output(blender).splitlines()]
    return ", ".join(line for line in lines if re.match(r"Blender \d|build \w+:", line))


def find_blender(version: str, explicit: Path | None) -> Path:
    if explicit:
        blender = explicit
        if blender.is_dir():
            blender = blender / exe("blender")
        if not blender.is_file():
            raise StepError(f"Blender binary {blender} does not exist")
    elif not is_release(version):
        blender = cached_blender(version)
        if not blender:
            raise StepError(
                f"No Blender build named {version!r}: build it with `mise run blender:build {version}` "
                "or pass --blender with a matching Blender binary"
            )
    else:
        blender = download_blender(version)

    actual = blender_binary_version(blender)
    if is_release(version) and actual != version:
        raise StepError(f"{blender} is Blender {actual}, but stubs for Blender {version} were requested")
    log(f"Using Blender {actual} binary {blender}")
    return blender


def run_blender_script(blender: Path, script: Path, *script_args: str | Path) -> None:
    run(blender_script_command(blender, script, *script_args))


def uv_python_cmd() -> list[str | Path]:
    """Python with fake-bpy-module's requirements installed (in an ephemeral uv environment)."""
    return [
        "uv",
        "run",
        "--no-project",
        "--python",
        ">=3.11",
        "--with-requirements",
        FAKE_BPY_SRC / "requirements.txt",
        "python",
    ]


def has_builtin_generator(source: Path) -> bool:
    """Whether the Blender source has its own stub generator (added in Blender 5.2)."""
    return (source / BUILTIN_STUB_GEN).is_file()


def resolve_generators(version: str, source: Path, generator: str) -> list[str]:
    """The generators ``generator`` (one of GENERATORS or ALL) stands for. ALL is fake-bpy-module and builtin, and
    leaves out the builtin generator for Blender versions without one (``source`` is the version's source
    worktree)."""
    if generator != ALL:
        return [generator]
    if has_builtin_generator(source):
        return [FAKE_BPY, BUILTIN]
    log(f"Blender {version} has no built-in stub generator ({BUILTIN_STUB_GEN.as_posix()}), using only {FAKE_BPY}")
    return [FAKE_BPY]


def tree_revision(repo: Path, *paths: str | Path) -> str:
    """HEAD of the git repository ``repo``, plus a hash of the uncommitted changes (untracked files included)
    under ``paths`` when there are any: ``<commit>`` or ``<commit>+dirty.<hash>``."""
    if not (repo / ".git").exists():
        # Otherwise git would describe the enclosing repository, e.g. for a submodule that is not checked out.
        raise StepError(f"{repo} is not a git checkout (run `git submodule update --init {repo.name}`?)")
    commit = git_output(repo, "rev-parse", "HEAD")
    pathspec = [Path(path).as_posix() for path in paths]
    if not git_output(repo, "status", "--porcelain", "--untracked-files=all", "--", *pathspec):
        return commit

    def git_bytes(*args: str) -> bytes:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout

    digest = hashlib.sha256(git_bytes("diff", "HEAD", "--binary", "--", *pathspec))
    untracked = git_bytes("ls-files", "--others", "--exclude-standard", "-z", "--", *pathspec)
    for name in sorted(filter(None, untracked.split(b"\0"))):
        digest.update(b"\0" + name + b"\0" + (repo / name.decode()).read_bytes())
    return f"{commit}+dirty.{digest.hexdigest()[:12]}"


def generator_revision(generator: str, source: Path) -> str:
    """What ``generator``'s stubs are generated by: the fake-bpy-module submodule's ``src/``, or Blender's stub
    generator in the source worktree ``source`` (whose commit the marker records anyway, but which may be edited
    in place). The runtime generator runs all of ``doc/python_api`` and the ``_rna_info`` module it reads RNA
    with."""
    if generator == FAKE_BPY:
        return tree_revision(FAKE_BPY_MODULE, FAKE_BPY_SRC.relative_to(FAKE_BPY_MODULE))
    if generator == RUNTIME:
        return tree_revision(source, PYTHON_API_DIR, RNA_INFO_MODULE)
    return tree_revision(source, BUILTIN_STUB_GEN)


def marker_fields(marker: str) -> dict[str, str]:
    """The ``key=value`` lines of a ``.complete`` marker."""
    return dict(line.split("=", 1) for line in marker.splitlines() if "=" in line)


def stale_reason(marker: str, commit: str | None, generator_rev: str | None, blender: str | None) -> str | None:
    """Why stubs whose ``.complete`` marker reads ``marker`` are out of date, given the source worktree's
    ``commit``, the stub generator's ``generator_rev`` and the ``blender_fingerprint`` of the Blender binary (None
    when unknown); None if they are current."""
    fields = marker_fields(marker)
    if commit is None or fields.get("commit") != commit:
        return "were generated from another Blender commit"
    if blender is None or fields.get("blender") != blender:
        return "were generated from another Blender build"
    if generator_rev is None or fields.get("generator_rev") != generator_rev:
        return "were generated by another version of the stub generator"
    return None


def results_name(stem: str, generator: str) -> str:
    """File name for results against ``generator``'s stubs (fake-bpy-module's keep the plain name)."""
    return f"{stem}.txt" if generator == FAKE_BPY else f"{stem}-{generator}.txt"


def rst_is_current(marker: str, commit: str, blender: str) -> bool:
    """Whether rst docs whose ``.complete`` marker reads ``marker`` came from the source ``commit`` and the Blender
    build with the ``blender_fingerprint`` ``blender``."""
    return marker_fields(marker) == {"commit": commit, "blender": blender}


def generate_rst(version: str, blender: Path, source: Path, force: bool) -> Path:
    """Return the rst API docs (``sphinx-in``) for ``version``, generating them with Blender if needed."""
    rst_dir = RST_DIR / version
    marker = rst_dir / COMPLETE_MARKER
    commit = git_output(source, "rev-parse", "HEAD")
    fingerprint = blender_fingerprint(blender)
    if marker.exists() and not force and rst_is_current(marker.read_text(), commit, fingerprint):
        log(f"Reusing rst documentation {rst_dir / 'sphinx-in'}")
        return rst_dir / "sphinx-in"
    shutil.rmtree(rst_dir, ignore_errors=True)
    rst_dir.mkdir(parents=True)
    log("Generating rst documentation with Blender (sphinx_doc_gen.py)")
    run_blender_script(blender, source / "doc" / "python_api" / "sphinx_doc_gen.py", "--output", rst_dir)
    marker.write_text(f"commit={commit}\nblender={fingerprint}\n")
    return rst_dir / "sphinx-in"


def generate_builtin_stubs(source: Path, rst: Path, stubs_dir: Path) -> None:
    log(f"Generating bpy stubs (Blender's {BUILTIN_STUB_GEN.as_posix()})")
    cmd: list[str | Path] = [
        "uv",
        "run",
        "--no-project",
        "--python",
        ">=3.11",
        "--with",
        "docutils",
        "python",
        source / BUILTIN_STUB_GEN,
        rst,
        "--output",
        stubs_dir,
    ]
    printable = " ".join(str(c) for c in cmd)
    print(f"    $ {printable}", flush=True)
    result = subprocess.run([str(c) for c in cmd], env={**os.environ, "PYTHONUTF8": "1"})
    if result.returncode == 0:
        return
    # It also fails on parse and documentation errors or failed validation after writing all stubs;
    # those stubs are still usable (and finding such errors is what the check tasks are for).
    if not any(stubs_dir.rglob("*.pyi")):
        raise StepError(f"Command failed with exit code {result.returncode}: {printable}")
    log(
        f"warning: {BUILTIN_STUB_GEN.name} exited with code {result.returncode} (errors above), "
        "keeping the stubs it wrote"
    )


def ensure_runtime_site() -> Path:
    """A folder with ``docutils`` for Blender's Python, installed once per RUNTIME_SITE_REQUIREMENT."""
    marker = RUNTIME_SITE_DIR / COMPLETE_MARKER
    if not marker.exists() or marker.read_text(encoding="utf-8") != RUNTIME_SITE_REQUIREMENT:
        shutil.rmtree(RUNTIME_SITE_DIR, ignore_errors=True)
        log(f"Installing {RUNTIME_SITE_REQUIREMENT} for the runtime stub generator into {RUNTIME_SITE_DIR}")
        run(["uv", "pip", "install", "--quiet", "--target", RUNTIME_SITE_DIR, RUNTIME_SITE_REQUIREMENT])
        marker.write_text(RUNTIME_SITE_REQUIREMENT, encoding="utf-8")
    return RUNTIME_SITE_DIR


def runtime_user_resources(version: str, blender: Path, source: Path) -> Path:
    """The user resources folder the runtime generator runs with: preferences with no add-on enabled, which its
    ``--write-preferences`` run saves once per Blender build and generator revision."""
    user = RUNTIME_USER_DIR / version
    marker = user / COMPLETE_MARKER
    fingerprint = f"{blender_fingerprint(blender)}\n{generator_revision(RUNTIME, source)}"
    if marker.exists() and marker.read_text(encoding="utf-8") == fingerprint:
        return user
    shutil.rmtree(user, ignore_errors=True)
    user.mkdir(parents=True)
    log(f"Saving preferences without add-ons for the runtime stub generator into {user}")
    command = blender_script_command(blender, source / RUNTIME_STUB_GEN, "--write-preferences")
    run(command, env={**os.environ, "BLENDER_USER_RESOURCES": str(user)})
    marker.write_text(fingerprint, encoding="utf-8")
    return user


def runtime_generator_command(
    version: str, blender: Path, source: Path, stubs_dir: Path, work: Path, addon: Path | None = None
) -> tuple[list[str], dict[str, str]]:
    """The command and environment that run the fork's ``runtime_stub_gen.py`` (with the add-on folder ``addon``
    enabled): from the preferences without add-ons, and without running the scripts of the files it opens."""
    args: list[str | Path] = ["--output", stubs_dir, "--work", work, "--python-path", ensure_runtime_site()]
    if addon is not None:
        args += ["--addon", addon]
    command = blender_script_command(blender, source / RUNTIME_STUB_GEN, *args, options=("-Y",), factory_startup=False)
    env = {**os.environ, "BLENDER_USER_RESOURCES": str(runtime_user_resources(version, blender, source))}
    return command, env


def generate_runtime_stubs(version: str, blender: Path, source: Path, stubs_dir: Path) -> None:
    work = RUNTIME_WORK_DIR / version
    shutil.rmtree(work, ignore_errors=True)
    log(f"Generating bpy stubs (the fork's {RUNTIME_STUB_GEN.as_posix()})")
    command, env = runtime_generator_command(version, blender, source, stubs_dir, work)
    run(command, env=env)


def generate_stubs(
    version: str,
    *,
    generator: str = FAKE_BPY,
    ref: str | None = None,
    blender: Path | None = None,
    force: bool = False,
    source: Path | None = None,
) -> Path:
    """Return the bpy stubs directory of ``generator`` for ``version``, generating the stubs if needed.

    ``source`` is the Blender source worktree when the caller has prepared it already; ``force`` then regenerates
    the stubs without recreating the worktree a second time.
    """
    stubs_dir = STUBS_DIRS[generator] / version
    marker = stubs_dir / COMPLETE_MARKER
    blender = find_blender(version, blender)
    if marker.exists() and not force:
        # Stubs go stale when the worktree moved to another commit (blender:build --update), Blender was rebuilt
        # (e.g. with other configure options) or the stub generator changed (a new fake-bpy-module submodule
        # commit, or uncommitted edits to its src/).
        commit = worktree_commit(version)
        generator_rev = generator_revision(generator, worktree_path(version)) if commit else None
        reason = stale_reason(marker.read_text(), commit, generator_rev, blender_fingerprint(blender))
        if reason is None:
            log(f"Reusing {generator} bpy stubs {stubs_dir}")
            return stubs_dir
        log(f"{generator} bpy stubs {stubs_dir} {reason}, regenerating them")

    source = source or ensure_worktree(version, ref, force)
    if generator == BUILTIN and not has_builtin_generator(source):
        raise StepError(
            f"Blender {version} has no built-in stub generator ({BUILTIN_STUB_GEN.as_posix()}, "
            f"added in Blender 5.2); use --generator {FAKE_BPY}"
        )
    if generator == RUNTIME and not (source / RUNTIME_STUB_GEN).is_file():
        raise StepError(
            f"The Blender {version} source has no runtime stub generator ({RUNTIME_STUB_GEN.as_posix()}, on the "
            f"fork's branch); use --generator {BUILTIN}"
        )

    # Taken before generating: fake-bpy-module writes its generated mod files into its own src/ (gitignored).
    generator_rev = generator_revision(generator, source)
    shutil.rmtree(stubs_dir, ignore_errors=True)
    if generator == RUNTIME:
        generate_runtime_stubs(version, blender, source, stubs_dir)
    else:
        # The rst docs stay cached, so the other generator (or a retry after a failure) can reuse them.
        rst = generate_rst(version, blender, source, force)
        if generator == BUILTIN:
            generate_builtin_stubs(source, rst, stubs_dir)
        else:
            generate_fake_bpy_stubs(version, blender, source, rst, stubs_dir)

    marker.write_text(
        f"blender={blender_fingerprint(blender)}\nblender_path={blender}\nsource={source}\n"
        f"commit={git_output(source, 'rev-parse', 'HEAD')}\ngenerator_rev={generator_rev}\n"
    )
    log(f"{generator} bpy stubs: {stubs_dir}")
    return stubs_dir


def blender_declares_node_sockets(rst: Path) -> bool:
    """Whether the rst docs state the socket each key of a built-in node gives (``bpy.types._ShaderNodeMath_inputs``,
    written by Blender's fork over every state of the node). fake-bpy-module's own generator then stands aside: it
    reads only a node's default state, and its classes would sit unused next to Blender's."""
    return next(rst.glob("bpy.types._*_inputs.rst"), None) is not None


def generate_fake_bpy_stubs(version: str, blender: Path, source: Path, rst: Path, stubs_dir: Path) -> None:
    # gen.py always reads generated mod files from this fixed location inside the submodule (gitignored).
    generated_mods = FAKE_BPY_SRC / "mods" / "generated_mods"
    shutil.rmtree(generated_mods, ignore_errors=True)
    generated_mods.mkdir(parents=True)
    gen_modfile = FAKE_BPY_SRC / "gen_modfile"
    try:
        log("Generating fake-bpy-module mod files")
        run_blender_script(
            blender,
            gen_modfile / "gen_external_modules_modfile.py",
            "-m",
            "addon_utils",
            "-o",
            generated_mods / "gen_modules_modfile",
            "-f",
            "rst",
        )
        run_blender_script(
            blender,
            gen_modfile / "gen_external_modules_modfile.py",
            "-m",
            "keyingsets_builtins",
            "-a",
            "-o",
            generated_mods / "gen_startup_modfile",
            "-f",
            "rst",
        )
        if not blender_declares_node_sockets(rst):
            run_blender_script(
                blender,
                gen_modfile / "gen_node_inputs_outputs_for_node_class.py",
                "-o",
                generated_mods / "gen_node_inputs_outputs_for_node_class",
                "-f",
                "rst",
            )
        bgl_source = next(
            (
                p
                for p in (
                    source / "source/blender/python/generic/bgl.cc",
                    source / "source/blender/python/generic/bgl.c",
                )
                if p.exists()
            ),
            None,
        )
        if bgl_source:
            (generated_mods / "gen_bgl_modfile").mkdir()
            run(
                uv_python_cmd()
                + [
                    gen_modfile / "gen_bgl_modfile.py",
                    "-i",
                    bgl_source,
                    "-o",
                    generated_mods / "gen_bgl_modfile" / "bgl.mod.rst",
                    "-f",
                    "rst",
                ]
            )

        log("Generating bpy stubs (fake-bpy-module gen.py)")
        # Same convention as fake-bpy-module's release tooling: the mod version is the Blender version.
        # For source builds (e.g. 'main') no mod version is passed, which applies all version-ranged mods.
        target_version = version if is_release(version) else "latest"
        mod_args = ["-m", version] if is_release(version) else []
        run(
            uv_python_cmd()
            + [
                FAKE_BPY_SRC / "gen.py",
                "-i",
                rst,
                "-o",
                stubs_dir,
                "-f",
                "ruff",
                "-T",
                "blender",
                "-t",
                target_version,
                "-l",
                "warn",
                *mod_args,
            ],
            cwd=FAKE_BPY_SRC,
        )
    finally:
        shutil.rmtree(generated_mods, ignore_errors=True)


def add_stubs_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "version",
        type=validate_version,
        help="Blender version as X.Y (e.g. 5.2), or the name of a Blender build from source (e.g. main)",
    )
    parser.add_argument("--ref", help="Blender git ref to check out instead of blender-vX.Y-release / the build name")
    parser.add_argument(
        "--blender",
        type=Path,
        help="Path to a Blender binary (or its directory) matching the version; by default the "
        "official release is downloaded into .cache/blender-bin/ (or built there by build_blender.py)",
    )
    parser.add_argument("--force", action="store_true", help="Recreate the source worktree and regenerate the stubs")
    parser.add_argument(
        "--generator",
        choices=(*GENERATORS, ALL),
        default=ALL,
        help=f"Stub generator (default: {ALL}, i.e. {FAKE_BPY} and {BUILTIN} where Blender has its own)",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    args = parser.parse_args()
    source = ensure_worktree(args.version, args.ref, args.force)
    for generator in resolve_generators(args.version, source, args.generator):
        generate_stubs(
            args.version, generator=generator, ref=args.ref, blender=args.blender, force=args.force, source=source
        )
    return 0


if __name__ == "__main__":
    main_wrapper(main)
