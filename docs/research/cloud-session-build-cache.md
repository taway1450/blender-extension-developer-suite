# A build cache for cloud sessions: ty and Blender without rebuilding from scratch

The platform limits and the host allowlist below were measured on 2026-11-17 and may change.

Research note, 2026-11-17. The question was whether a Claude Code cloud session could download a ready
cache instead of compiling ty and Blender, which ways there are to do that, and how they compare. A
requirement added during the research: the cache has to keep **incremental** builds working. After the
cache is restored, an edit in `ty-blender/ruff-blender` (or in the Blender source) followed by the same
mise task must rebuild incrementally (about 25 s for ty's dev profile, `AGENTS.md`), not from scratch. A
cache that only ships final binaries does not meet that requirement.

Every fact has a source next to it: a URL, a `path:line` in this repo or its submodules, or a command run
in this cloud session (*verified locally*, with the date 2026-11-17). My own recommendations are marked
**Recommendation**. Nothing here was built: the sizes come from the ty build that the environment's setup
script had already made in this session, and no Blender build exists in this container (`.cache/` is
absent).

---

## 0. Measured results for ty (2026-11-23)

A prototype of option B (section 5), measured in a cloud session (4 vCPU, `SUITE_JOBS` unset, so 2 cargo jobs),
at `ruff-blender` 3872f740fc. The script is
[cloud-session-build-cache/ty_restore_proto.py](cloud-session-build-cache/ty_restore_proto.py). Every build ran
through `mise run ty:build`. A "fresh clone" was simulated by giving every file in `ruff-blender` the current
time, which is what `git clone` does.

### 0.1 Timings

| Scenario | Time | Crates compiled |
| --- | --- | --- |
| Cold build (empty `target/`, toolchain and registry already present) | **8 min 40 s** | 297 |
| No-op rebuild | 0.9 s | 0 |
| A 6-day-old `target/` (11-17) after the submodule moved to the 11-19 commit (new `Cargo.lock`) | 7 min 02 s | 99 (62 third-party) |
| Restored `target/`, fresh clone, **no mtime repair** | 30 s | 37 (all workspace crates; rustc reuses its incremental data) |
| Restored `target/`, fresh clone, repair backdates files only | 23–25 s | 7 (`ty_vendored` and everything after it) |
| Restored `target/` built from backdated sources, fresh clone, repair of files and directories | **1.4 s** | 0 |
| Then a one-line edit in `ty_python_semantic` | 20 s | 5 |
| Then reverting the edit | 19 s | 5 |

The pieces of a restore:

| Step | Time / size |
| --- | --- |
| `target/` after a cold build | 3.9 GB |
| `tar | zstd -T0 -3` of it | **1.17 GB** (1.62 GB after a few more incremental builds, which grow `incremental/`) |
| Pack | 8–11 s |
| Extract | 15–18 s |
| mtime repair (12,341 paths) | under 1 s |
| Download at the 25 MB/s measured from GitHub releases (`blender-build-cache-hosting.md` section 0) | ~47 s (estimate) |

### 0.2 What the prototype found that the reading in 3.1 missed

- **Without any repair a restored `target/` is already good.** Cargo reruns rustc on the 37 workspace crates,
  but rustc finds nothing changed in its incremental data, so the fresh clone costs 30 s rather than 8 min.
  That is the opposite of Blender, where a fresh checkout makes Ninja recompile everything.
- **Backdating sources only after the restore is not enough.** `ty_vendored`'s build script prints no
  `rerun-if-changed`. Cargo then fingerprints the package by its newest mtime and stores that time as a value.
  Backdating changes the value, so cargo reruns the build script, which rezips typeshed, and everything that
  depends on `ty_vendored` recompiles. This is my reading of the behaviour, not of cargo's source: backdating
  before the build fixed it (next point). The fix is to backdate the sources (directories included)
  *before* the CI build too, so the recorded value is the same `EPOCH` the restore sets.
- **A stale cache is nearly worthless after a dependency bump.** The 6-day-old `target/` saved only 1.5
  minutes, because the new commit changed `Cargo.lock` (35 of the 452 commits in the last month touch it,
  most of them upstream's dependency updates). So the cache has to follow every `ty-blender` pointer bump,
  not be rebuilt weekly.

### 0.3 Setup time with and without the cache

The platform snapshots the environment only "when setup completes within roughly five minutes" (section 4).
The other steps of the current setup script, measured in this session where possible:

| Setup step | Time |
| --- | --- |
| `blender` submodule, `--filter=blob:none`, no LFS (clone + checkout) | 48 s |
| Rust 1.99.0 toolchain (`rustup toolchain install`, 1.5 GB) | 30 s |
| `apt-get update` | 5 s |
| apt install (GCC 14, X/Wayland headers), ccache, mise, plugin, the other submodules, crate registry | not measured; ~1.5–2 min estimated |
| **ty today: `mise run ty:build`** | **8 min 40 s** |
| **ty with the cache: download + extract + repair + no-op build** | **~65 s** |

Without the cache setup takes about 12 minutes, far over the window. So most likely no snapshot is ever
taken, and every new session waits for that setup before it starts. With the cache, the estimate is about
4–4.5 minutes, near the limit, so whether the snapshot then forms is not certain.

### 0.4 Is it worth it?

**Yes, but it is a smaller win than the Blender cache, and it relies on one assumption.** It saves about
7.5 minutes per new session for certain. The bigger prize is the snapshot: if setup gets under 5 minutes,
sessions skip setup entirely for 7 days. That part is not verified (open question 2 still stands, and the
estimate in 0.3 is close to the limit). The cost is small, because `scripts/blender_cache.py` already does
pack, restore, the manifest and the release rotation: the ty variant is a second archive, the backdate step
before the build, and a workflow trigger on `ty-blender` pointer bumps (~9 minutes of free CI each).

*Found in CI:* cargo 1.99 turns incremental compilation off by default when `CI` is set, which GitHub's runners
always do. The first CI cache therefore had no `incremental/` data and different fingerprints: restored here, it
recompiled all 37 workspace crates (6.5 min). `ty:cache-pack` now unsets `CI` and the `CARGO_*INCREMENTAL`
variables before building and refuses a `target/` without incremental data. Verified with a one-file crate: without
`CI` rustc gets `-C incremental=…`, with `CI=true` it does not.

*Built since:* `mise run ty:restore` / `ty:cache-pack` (`scripts/ty_cache.py`, sharing `scripts/_build_cache.py`
with the Blender cache) and `.github/workflows/ty-cache.yml`, which runs on every `ty-blender` bump on main. Tested
end to end here through a local HTTP server: after a simulated fresh clone the next `ty:build` was a 0.6-s no-op,
and with `ruff-blender` one commit ahead of the cache (one file in `ty_python_semantic`) it rebuilt 5 crates in 22 s.

Cheaper alternatives considered:
- **Drop `ty:build` from the setup script.** Setup then likely fits the window, the snapshot forms, and the
  first task in each session pays 8.7 minutes instead. The snapshot would not have ty, so every session
  still pays the build, just later.
- **sccache.** Not useful: it skips the incremental workspace crates, which are what an edit rebuilds (3.2).
- **A weekly cache instead of per-bump.** Not useful: the measurement above shows a stale `target/` is nearly
  a cold build.

---

## 1. Summary

- **Today every cloud session pays for a full ty build in the setup script, and the platform's own
  cache never kicks in.** The environment's setup script ends with `mise run ty:build` (setup script,
  read with `get_environment`). In this session that build ran from 12:55:30 to 13:03:36, about 8 minutes
  (*verified locally*: mtimes of `target/debug/.fingerprint` and `target/debug/ty`). The platform
  snapshots the filesystem after setup only "when setup completes within roughly five minutes"
  ([cloud-environments#environment-caching](https://code.claude.com/docs/en/cloud-environments#environment-caching)).
  So this environment is most likely never cached, and every new session repeats the 8-minute build.
- **Recommendation: the setup script downloads a cargo `target/` tarball that CI built at the same
  absolute path with the same toolchain, then sets source mtimes so that cargo treats it as fresh.** The
  environment snapshot then keeps it for about 7 days. Cargo's freshness check ignores absolute paths but
  compares mtimes (section 3.1), so the restored `target/` keeps rustc's `incremental/` data and the next
  edit rebuilds in the usual ~25 s. The tarball is 1.37 GB with `gzip -1` (*verified locally*), under
  GitHub's 2 GiB limit per release asset, and `release-assets.githubusercontent.com` is on the default
  allowlist. It downloaded at ~21 MB/s here (*verified locally*), so about 1 minute.
- **Blender has no cheap answer that stays incremental.** A Blender build can't finish inside the
  5-minute setup window. A restored CMake/Ninja build directory goes stale as soon as git checks out the
  sources again, because Ninja compares mtimes. ccache, which hashes file contents, is the option that
  survives a fresh checkout, at the cost of recompiling through cache hits and of several GB of cache
  (section 3.3). For most tasks a cloud session needs Blender's *outputs* (the binary, `bpy-rst`, the
  stubs), not its build tree. Shipping those as a fallback archive covers every task except editing
  Blender's C/C++ code.

## 2. What gets built, how big it is, and what invalidates it

### 2.1 ty (cargo, `ty-blender/ruff-blender`)

- **What.** `cargo build --profile dev --bin ty` in `ty-blender/ruff-blender` (`scripts/build_ty.py:74`).
  The binary is expected at `ty-blender/ruff-blender/target/<profile dir>/ty`, with the target directory
  hard-coded (`scripts/build_ty.py:36-37`). The `dev` profile is `opt-level = 1`,
  `debug = "line-tables-only"` and `lto = "off"` (`ty-blender/ruff-blender/Cargo.toml:351-355`).
  Cargo turns on incremental compilation by default for this profile, for workspace members only
  (sccache README, quoted in 3.2). The `profiling` profile gets `CARGO_PROFILE_PROFILING_INCREMENTAL=true`
  from the script (`scripts/build_ty.py:32-33,72-73`).
- **Jobs.** Every task sets `CARGO_BUILD_JOBS` to half the logical CPUs (`scripts/_resources.py:9-11,29-35`).
  On the cloud VM (4 vCPU: [cloud-environments#resource-limits](https://code.claude.com/docs/en/cloud-environments#resource-limits);
  `nproc` = 4, *verified locally*) that is 2 jobs.
- **Cost (*verified locally*).** A clean dev build took about 8 min, and `target/` is 3.8 GB: `debug/deps`
  1.6 GB, `debug/incremental` 1.8 GB, `debug/build` 509 MB, `.fingerprint` 7.9 MB. The `ty` binary alone
  is 256 MB. `tar | gzip -1` of the whole `target/` is 1,367,428,829 bytes. Before that, the toolchain
  pinned in `ty-blender/ruff-blender/rust-toolchain.toml` (`channel = "1.99.0"`) took 1.2 GB in
  `~/.rustup`, and the crate registry 278 MB in `~/.cargo/registry`.
- **An incremental rebuild** after a change takes about 25 s, and a no-op one about 1 s (`AGENTS.md`,
  "Editing the typechecker").
- **What invalidates it** (cargo's fingerprint table, quoted in 3.1): the rustc version, the profile,
  features, RUSTFLAGS, the dependency graph (`Cargo.lock`), and the mtimes of the workspace's source files.
  In practice the cache key is: the `ruff-blender` commit (which covers `Cargo.lock` and
  `rust-toolchain.toml`), the profile, the target triple (x86_64 Linux; `uname -m`, *verified locally*),
  and, to stay safe, the absolute checkout path (3.1).

### 2.2 Blender from source (`blender:build`)

- **What.** `blender:build <name>` creates a git worktree of the `blender` submodule in
  `.cache/blender-src/<name>`, pulls its LFS files, and checks out the precompiled libraries in a shared
  clone, `.cache/blender-libs/<platform>` (`scripts/build_blender.py:7-16,71-107`). It configures CMake +
  Ninja in `.cache/blender-build/<name>` and installs into `.cache/blender-bin/<name>`
  (`scripts/build_blender.py:195-232`).
- **Which ref.** The `blender` submodule points at a fork, `projects.blender.org/Simon-Sak/blender`
  (`.gitmodules`). Its checked-out commit differs from its merge base with `origin/main` in 372 `.cc`, 171
  `.hh`, 55 `.h`, 32 `.cpp` and 141 `.py` files (*verified locally*, `git diff --name-only`). So the fork's
  `main` is not upstream's `main`, and its C/C++ changes are real.
- **When it is reused.** Only when `.cache/blender-bin/<name>/.build-info` names the same commit, config and
  build type (`scripts/build_blender.py:175-183`). The CMake configure step is skipped when
  `configure-args.txt` matches (`scripts/build_blender.py:214-228`). Every path passed to CMake is absolute
  (`-S`, `-B`, `LIBDIR`, `CMAKE_INSTALL_PREFIX`; `scripts/build_blender.py:200-213`).
- **Cost.** Not measured: no Blender build exists in this container. The README says it "takes a while
  and needs several GB for libraries and build" (`README.md:36`). Blender's own CMake notes that "a debug
  ASAN build on Linux can approach 4GB" of ccache, and asks for at least 16 GB of ccache
  (`blender/build_files/cmake/compiler_ccache_max_size_check.cmake:10-18`).
- **Downstream outputs.** `stubs:generate` caches the rst docs in `.cache/bpy-rst/<version>` and the stubs in
  `.cache/bpy-stubs[-builtin]/<version>` (`scripts/generate_stubs.py:61-62`). It reuses them while the
  worktree's commit and the generator revision match the `COMPLETE_MARKER` (`scripts/generate_stubs.py:339-349`).
  Only regenerating them needs a Blender binary (`scripts/generate_stubs.py:358-364`). So `check:features`,
  `check:ide` and `check:oracle` need Blender's outputs, not a Blender build tree. `check:load` needs the
  Blender binary.

## 3. How incremental builds survive (or don't) a restore

### 3.1 Cargo: the target dir survives a move but not new mtimes

Source: cargo `src/compiler/fingerprint/mod.rs` at commit `ef7d397` (rust-lang/cargo, 2026-11-17),
[mod.rs](https://github.com/rust-lang/cargo/blob/ef7d397521b89707178dbb853f56510a91a75add/src/compiler/fingerprint/mod.rs).

- **Mtimes decide freshness for workspace crates.** "[`CheckDepInfo`] … compares the mtime of the input files
  (the source files) to the mtime of the dep-info file" (mod.rs:236-243). Registry and git packages list no
  source files in dep-info, "so for those kinds no mtime checking is done" (mod.rs:245-249). Build scripts
  with `rerun-if-changed` also compare mtimes (mod.rs:271-285).
- **Absolute paths are kept out on purpose.** "if you rename a project directory Cargo will continue to
  preserve all build artifacts and reuse the cache. This means that we can't ever hash an absolute path
  name… Some of this is best effort" (mod.rs:304-312). Path packages hash their path *relative to the
  workspace root* (`src/workspace/source_id.rs:567-579`).
- **Content hashes instead of mtimes are nightly-only.** `-Z checksum-freshness` "will replace the use of file
  mtimes in cargo's fingerprints with a file checksum value… most useful … in CI/CD", but it is still listed
  under unstable features (`doc/book/src/reference/unstable.md:619-636`, tracking issue
  [#14136](https://github.com/rust-lang/cargo/issues/14136)). It needs nightly rustc (mod.rs:36-40). This
  repo pins stable 1.99.0.
- **What a fresh `git clone` does.** git sets every file's mtime to the time of the checkout. Every source file
  of every workspace crate is then newer than its dep-info, so cargo reruns rustc for all ~40 workspace crates
  that `incremental/` holds data for (*verified locally*: the crate names under `target/debug/incremental`).
  The third-party crates in `deps/` stay fresh. rustc then reuses its incremental data, so this is not a
  clean build. But it is not the 1-s no-op either, and I could not measure it without building (open question 1).
- **The fix is cheap:** after restoring `target/`, set the mtime of every tracked file in `ruff-blender` that
  did not change since the cache's commit to a time before the cache was built. One way:
  `git diff --name-only <cache commit> HEAD` gives the files to keep at "now", and
  `touch -d @<old>` goes on the rest. Cargo's freshness then sees exactly the files that really changed,
  which gives the incremental rebuild the requirement asks for. This is my reading of the mtime rules above,
  not something I ran. *Measured later (section 0.2):* the sources also have to be backdated before the CI
  build, and directories too, or `ty_vendored` and the 6 crates after it rebuild.
- **Keep the path the same anyway.** Cargo tries to be path-independent "best effort", and I did not verify
  whether rustc's `incremental/` data is reused from another path. The cloud checkout is always
  `/home/user/blender-extension-developer-suite` (*verified locally*), so the cache should be built at that
  path, as root, with `CARGO_HOME=/root/.cargo`.

### 3.2 sccache does not cache incremental crates

- "Incrementally compiled crates cannot be cached. By default, in the debug profile Cargo will use
  incremental compilation for workspace members and path dependencies" (sccache README, "Known Caveats → Rust",
  [README.md](https://github.com/mozilla/sccache/blob/main/README.md#rust)). Also: "Crates that invoke the
  system linker cannot be cached. This includes `bin`…", so the final `ty` link is never cached either.
- With `SCCACHE_ALLOW_INCREMENTAL=1` "only the incremental crates (workspace members and path dependencies)
  go uncached" ([docs/Rust.md](https://github.com/mozilla/sccache/blob/main/docs/Rust.md)).
- "By default, absolute paths to files must match to get a cache hit", unless `SCCACHE_BASEDIRS` is set (README).
- **Consequence for ty:** under the dev profile sccache caches only the third-party crates, which a restored
  `target/` already has. The ~40 workspace crates, where the 25-s rebuilds happen, are never cached.
  Turning incremental off (`CARGO_INCREMENTAL=0`) would make them cacheable, but then every edit recompiles
  the whole crate (`ty_python_semantic` is the big one) instead of rebuilding incrementally. That trade goes
  against this repo's choice of an incremental dev profile (`scripts/build_ty.py:4-5`).

### 3.3 Ninja and ccache (Blender)

- **Ninja works only from mtimes.** It "runs whichever commands are necessary to make your build target up to
  date as determined by file modification times" ([ninja manual](https://github.com/ninja-build/ninja/blob/master/doc/manual.asciidoc),
  "Conceptual overview"). A build directory restored next to a freshly checked-out source tree sees every source
  newer than its objects and rebuilds everything. The same mtime fix as in 3.1 applies, but it has to cover
  the whole Blender worktree and the `lib/` checkout. On top of that, the worktree's git metadata lives in the
  superproject's `.git/modules/blender/worktrees/`, so `ensure_worktree` re-creates it
  (`scripts/generate_stubs.py:129-141`), which rewrites every file.
- **CMake paths.** The build directory is configured with absolute paths (`scripts/build_blender.py:200-213`),
  so a build directory only makes sense at the same path. CMake's refusal to reuse a `CMakeCache.txt` from
  another source directory is well known, but I did not check it against CMake's source.
- **ccache hashes content, so it survives a fresh checkout.** Its direct mode hashes the source and its
  includes. For "builds with absolute paths, set *base_dir* to a common parent directory. Ccache will convert
  absolute paths under this directory to relative paths before hashing"
  ([ccache manual, "Compiling in different directories"](https://github.com/ccache/ccache/blob/master/doc/manual.adoc)).
  `remote_storage` accepts `file:`, `http://` and `redis://` backends (same manual, `config_remote_storage`).
- **Blender supports it.** `WITH_COMPILER_CCACHE` ("Use ccache to improve rebuild times (Works with Ninja,
  Makefiles and Xcode)", `blender/CMakeLists.txt:1249-1253`) sets `CMAKE_C(XX)_COMPILER_LAUNCHER` to ccache
  (`blender/build_files/cmake/platform/platform_unix.cmake:1109-1115`). ccache is not installed in the cloud
  image (`which ccache` is empty, *verified locally*). It is an `apt install` away (the setup script runs as
  root on Ubuntu 24.04, [cloud-environments#setup-scripts](https://code.claude.com/docs/en/cloud-environments#setup-scripts)).
- **What it buys.** After a fresh checkout Ninja still runs every compile command, but each one is a cache hit,
  and every link runs for real. After that one pass, Ninja is incremental again. So ccache meets the
  requirement after one "replay" build, whose length I could not measure (open question 3).

## 4. What the cloud platform offers (sourced from the Claude Code docs)

- **Environment cache.** "When setup completes within roughly five minutes, Anthropic snapshots the
  filesystem and reuses that snapshot as the starting point for later sessions… skip the setup script step."
  It is rebuilt "when you change the environment's setup script or allowed network hosts, and when the cache
  reaches its expiry after roughly seven days" ([cloud-environments#environment-caching](https://code.claude.com/docs/en/cloud-environments#environment-caching)).
  Being a filesystem snapshot, it keeps files but not running processes (same section).
- **No custom image.** "Replacing the base image entirely isn't supported yet". Docker images can run
  alongside, and pulled images are kept by the environment cache
  ([cloud-environments, end of "Install dependencies with a SessionStart hook"](https://code.claude.com/docs/en/cloud-environments#install-dependencies-with-a-sessionstart-hook);
  [#installed-tools](https://code.claude.com/docs/en/cloud-environments#installed-tools)).
- **Limits.** 4 vCPUs, 16 GB RAM, 30 GB disk ([#resource-limits](https://code.claude.com/docs/en/cloud-environments#resource-limits)).
  The setup script must exit 0 and should finish in about 5 minutes ([#script-requirements](https://code.claude.com/docs/en/cloud-environments#script-requirements)).
- **SessionStart hooks** from the repository's `.claude/settings.json` run "on every session including resumed",
  in a session with a single repository (the case here) ([#setup-scripts-vs-sessionstart-hooks](https://code.claude.com/docs/en/cloud-environments#setup-scripts-vs-sessionstart-hooks)).
  They are cancelled after 600 s unless they set `timeout` or `async: true` ([#time-limits](https://code.claude.com/docs/en/cloud-environments#time-limits)).
  This repo has no `.claude/settings.json` yet (*verified locally*).
- **Secrets.** Network secrets are headers that the proxy injects. They are never attached to "Setup script
  requests" ([#requests-that-never-get-the-secret](https://code.claude.com/docs/en/cloud-environments#requests-that-never-get-the-secret)).
  So a download in the setup script must need no credentials. Environment variables are readable by anyone
  who uses the environment ([#set-environment-variables](https://code.claude.com/docs/en/cloud-environments#set-environment-variables)).
- **Idle VMs** pause "with its files saved" and can later be reclaimed (#time-limits). This session's
  `target/` survived such a pause: `uptime -s` says 14:36, `target/` dates from 12:55 (*verified locally*).
- **This environment** (`get_environment`): Limited network with package managers, plus
  `download.blender.org` and `projects.blender.org`. The setup script installs mise from a GitHub release,
  initialises the submodules (the `blender` one with `--filter=blob:none` and no LFS), and runs `mise run ty:build`.

### 4.1 Which hosts each option needs (*verified locally* with `curl` through the session proxy)

| Host | Default allowlist (docs) | Reachable here |
| --- | --- | --- |
| `github.com`, `release-assets.githubusercontent.com`, `objects.githubusercontent.com` | yes | yes (a release asset downloaded, 206) |
| `ghcr.io` | yes | yes (token and manifest, 200) |
| `pkg-containers.githubusercontent.com` (where ghcr.io redirects blob downloads) | **no** | **no**: 403 from the proxy; a ghcr blob GET answered 307 to this host |
| `*.blob.core.windows.net`, `results-receiver.actions.githubusercontent.com`, `pipelines.actions.githubusercontent.com` (Actions artifacts/cache) | no | no (403) |
| `*.amazonaws.com` (S3) | yes | yes (`s3.us-east-1.amazonaws.com` 307, a bucket host 404) |
| `*.r2.cloudflarestorage.com` | yes | not tested with a real account; the bare `r2.cloudflarestorage.com` is refused (403) |
| `pub-*.r2.dev` (R2 public buckets) | no | not tested |
| `storage.googleapis.com` | yes | yes |
| `builder.blender.org` (daily builds) | no | **no** (403) |
| `download.blender.org`, `projects.blender.org` | no (added by this environment) | yes |
| `lfs.github.com` | no | no (403); `media.githubusercontent.com` answers 302 |

Default list: [cloud-environments#default-allowed-domains](https://code.claude.com/docs/en/cloud-environments#default-allowed-domains).
Adding a host to the environment invalidates its cache (4, first bullet).

## 5. The options

### A. Environment cache alone (setup script builds; the platform snapshots)

- **How it works.** The setup script builds, the platform snapshots the result, and later sessions start from
  the snapshot. Nothing to host.
- **Incremental.** Yes in principle: a filesystem snapshot should keep `target/` with its mtimes. Whether the
  repo checkout itself is part of the snapshot or re-cloned is undocumented (open question 2).
- **Blocker.** The 5-minute window. ty alone takes ~8 min at 2 jobs (2.1). `SUITE_JOBS=4` in the setup script
  might bring that close to 5 minutes (unmeasured), before cloning the submodules. A Blender build is far out
  of reach.
- **Effort.** Edit the setup script only.

### B. CI builds `target/`, published as a GitHub Release asset, and restored in setup (combined with A)

- **How it works.** A workflow on `ubuntu-24.04` (Linux x64, 4 CPU, 16 GB RAM, 14 GB SSD for public repos,
  free and unlimited: github/docs `data/reusables/actions/supported-github-runners.md`) runs as root in an
  `ubuntu:24.04` container. It checks out at `/home/user/blender-extension-developer-suite` with
  `CARGO_HOME=/root/.cargo` and runs `mise run ty:build` (the same toolchain via `rust-toolchain.toml`). It
  tars `ty-blender/ruff-blender/target` with a manifest (`ruff-blender` commit, rustc version, profile,
  build start time) and uploads it as a release asset named after the key. The setup script downloads the
  asset for the commit it has checked out, falls back to the newest one, applies the mtime fix (3.1), and runs
  `mise run ty:build`, which is then a no-op or an incremental rebuild of what changed.
- **Incremental.** **Yes**: the restored `incremental/` and fingerprints are what make the 25-s rebuilds.
- **Limits.** "Each file included in a release must be under 2 GiB", with no limit on total size or bandwidth
  (github/docs `content/repositories/releasing-projects-on-github/about-releases.md:49`,
  `data/variables/large_files.yml`). 1.37 GB with gzip -1 fits; zstd would leave more room (zstd is not
  installed in the cloud image, *verified locally*, but is in apt). A job runs for at most 6 hours
  (github/docs `content/actions/reference/limits.md:45`).
- **Hosts / auth.** `github.com` and `release-assets.githubusercontent.com`, both default. The repo is public
  (`private: false` from `api.github.com`, *verified locally*), so no token is needed, which matters because
  the setup script gets no secrets.
- **Time.** ~21 MB/s from a GitHub release (*verified locally*, 200 MB in 10 s), so ~65 s for 1.37 GB, plus
  extraction. That fits the 5-minute window with room for the submodule clones, so the environment snapshot
  forms and later sessions skip even the download.
- **Failure modes.** No asset for the checked-out commit: the mtime fix keeps files that differ from the cache
  commit at "now", so cargo rebuilds those crates incrementally, which still beats a clean build. A rustc or
  path mismatch: cargo rebuilds (correct, just slow). A corrupted download: verify a checksum before extracting.
  Stale-but-fresh risk: if the mtime fix wrongly backdates a file that changed, cargo would skip it. So the
  fix has to come from `git diff` against the recorded cache commit, never be blanket.
- **Effort.** A new workflow (`.github/workflows/`, none exists yet), about 30 lines of setup script, and
  optionally a `cache:restore` mise task so the logic lives in `scripts/` and gets tested by `test:scripts`.
  No change to `build_ty.py`.

### C. The same, through ghcr.io (OCI artifact via oras) or Docker Hub

- **Like B**, with content-addressed tags and no 2 GiB file limit (layers can be split). But ghcr.io serves blobs
  from `pkg-containers.githubusercontent.com`, which the proxy refuses (4.1). That host would have to be added
  to the environment, which is allowed but invalidates the cache once. Docker Hub hosts
  (`registry-1.docker.io`, `production.cloudflare.docker.com`) are on the default list (docs), but I did not
  test a pull. **Incremental:** yes, same as B. **Effort:** a bit more than B (oras or a docker image as a
  file carrier).

### D. GitHub Actions artifacts or the Actions cache, read directly

- **Artifacts:** the download endpoint returns a redirect, and "OAuth tokens and personal access tokens
  (classic) need the `repo` scope" (github/docs REST description of the artifact download endpoint,
  `src/rest/data/fpt-2022-11-28/actions.json`). The redirect goes to Azure blob storage, which the proxy
  refuses (4.1). Retention is 90 days by default (github/docs `data/reusables/actions/artifact-log-retention-statement.md`).
- **Actions cache:** only inside a workflow run. sccache's GHA backend "will need tokens like
  `ACTIONS_RESULTS_URL` and `ACTIONS_RUNTIME_TOKEN`" ([sccache docs/GHA.md](https://github.com/mozilla/sccache/blob/main/docs/GHA.md)).
  The cache holds 10 GB per repo and evicts entries not accessed for 7 days
  (github/docs `content/actions/reference/workflows-and-actions/dependency-caching.md:357-359`).
- **Verdict:** not usable from a cloud session. The Actions cache is still useful *inside* the CI job of
  option B, to make that job incremental.

### E. sccache with a remote backend (S3, R2, GCS, WebDAV)

- **Incremental:** **no** for the workspace crates that change (3.2). It caches the third-party crates and
  nothing else, and a restored `target/` already gives you those for free.
- **Auth:** the S3, R2 and GCS backends sign their requests themselves, so the credentials would have to sit in
  environment variables, which anyone using the environment can read (4). A network secret only injects a
  fixed header, and I did not verify whether that fits any sccache backend. Not in the setup script either way (4).
- **Verdict:** not worth it for ty's dev profile. It would only matter if the repo moved to
  `CARGO_INCREMENTAL=0`.

### F. ccache for Blender (local cache dir shipped as an archive, or `remote_storage`)

- **How it works.** CI (or one cloud session) builds Blender with `-DWITH_COMPILER_CCACHE=ON` and
  `CCACHE_BASEDIR=/home/user/blender-extension-developer-suite`. The ccache directory is published (option B's
  channel, split under 2 GiB per asset), or served over `http://`/`redis://` `remote_storage`. A session restores
  it and runs `blender:build`.
- **Incremental:** **partly**. The first build after a restore replays every compile as a cache hit and relinks.
  After that, Ninja is incremental as long as the build directory stays (within a session, or in the snapshot).
- **Limits.** Size: probably several GB (Blender recommends at least 16 GB of cache for switching branches;
  3.3). Cache plus libraries plus build directory plus install has to fit in 30 GB of disk, next to ty's 3.8 GB.
  The CI side is doubtful: the 14 GB runner SSD is likely too small for a full build (open question 4).
- **Effort.** High: a CI job for Blender, a `--ccache` flag in `scripts/build_blender.py`, and an
  `apt install ccache` in setup.

### G. Restore Blender's build dir, install dir and worktree with mtime repair

- **Incremental:** **yes**, if the paths are identical and the worktree's mtimes are repaired the way 3.1
  describes. But the worktree has to be re-created through git first (3.3).
- **Limits.** The largest archive of all (build directory, libraries, install). It doesn't fit the 2 GiB
  asset limit without splitting, and doesn't fit the 5-minute setup window, so it can't live in the snapshot.
  Each session would download it in a SessionStart hook, at ~18–21 MB/s.
- **Verdict:** possible, but fragile and heavy. Not recommended unless C/C++ work on Blender in cloud
  sessions becomes common.

### H. Blender daily builds (builder.blender.org) or a final Blender archive

- `builder.blender.org` has a JSON listing (`/download/daily/?format=json&v=1`;
  [wiki: BuildBot](https://wiki.blender.org/wiki/Tools/buildbot/),
  [blender-buildbot-www PR #1](https://projects.blender.org/infrastructure/blender-buildbot-www/pulls/1)).
  It builds upstream branches, not the `Simon-Sak` fork, whose C/C++ differs (2.2). The host is not allowed
  here (4.1). `scripts/download_blender.py` only knows releases from `fake-bpy-module/src/versions.yml`
  (`scripts/download_blender.py:55-68`).
- **A final-output archive** of this repo's own `main` build (`.cache/blender-bin/main` with `.build-info`,
  `.cache/bpy-rst/main`, `.cache/bpy-stubs*/main`) is different. Published like B, it lets
  `build_blender` short-circuit on a matching `.build-info` (`scripts/build_blender.py:175-183`) and lets the
  stubs be reused (2.2). **Incremental:** **no**, since a Blender C/C++ edit means a full build. But it
  covers every check task.

### I. Git LFS in this repo

- Up to 2 GB per file on Free/Pro, and only 10 GiB of storage and 10 GiB of bandwidth per month included
  (github/docs `about-git-large-file-storage.md:25-30`, `data/variables/large_files.yml`). One 1.4 GB
  download per session uses up the month's bandwidth in about 7 sessions. `lfs.github.com` is refused here (4.1).
- **Verdict:** no.

### J. Your own object storage (S3 / R2 / GCS), content-addressed

- **Like B**, without GitHub's limits. Key = hash(`ruff-blender` commit, profile, rustc, path). A
  public-read S3 bucket works over `*.amazonaws.com` with no credentials, which the setup script requires
  (4.1). R2 has free egress and $0.015/GB-month of storage after 10 GB-month free
  ([R2 pricing](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/r2/pricing.mdx)).
  But its public URLs are on `r2.dev` or a custom domain, which are not on the default list.
- **Incremental:** same as B. **Effort:** same as B, plus an account, a bucket and CI credentials.
- **Verdict:** use it if GitHub Releases' 2 GiB limit gets in the way (for example for the Blender archives
  of F/G/H).

### K. Not caching: Remote Control or a self-hosted environment

- Cloud sessions can run "on your organization's self-hosted environment", and the docs point to
  [Remote Control](https://code.claude.com/docs/en/remote-control.md) "for workloads beyond these limits"
  ([#resource-limits](https://code.claude.com/docs/en/cloud-environments#resource-limits)). On your own machine,
  `.cache/` and `target/` simply persist. **Incremental:** yes, natively. This is the only option where
  Blender C/C++ work is as fast as locally, and it needs no hosting. The cost is a machine that is on.

## 6. Comparison

| Option | Keeps incremental rebuilds? | ty | Blender | Hosts beyond default | Auth in setup | Size / retention limits | Effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A. Env cache alone | Yes (snapshot keeps mtimes; repo handling unverified) | only if setup < 5 min (today ~8 min) | no | none | none | snapshot ~7 days | trivial |
| **B. CI `target/` → Release asset, + A** | **Yes** (same path + mtime fix) | **yes** | no | none | none (public repo) | 2 GiB/asset (1.37 GB gzip) | medium |
| C. Same via ghcr.io / Docker Hub | Yes | yes | possible | `pkg-containers.githubusercontent.com` | none (public) | none practical | medium+ |
| D. Actions artifacts / cache directly | — | unusable | unusable | Azure blob hosts | `repo` token / runtime token | 90 d / 10 GB, 7 d | — |
| E. sccache remote | **No** (incremental crates never cached) | deps only | (C/C++ yes) | bucket host | creds in env vars | backend's | medium |
| F. ccache for Blender | Partly (one replay build, then yes) | — | yes | none (via B) or cache host | none for public archive | several GB; 30 GB disk | high |
| G. Blender build dir + mtime repair | Yes (fragile) | — | yes | none | none | very large; no snapshot | high |
| H. Final Blender outputs archive / daily builds | **No** (final binary only) | — | checks only | none / `builder.blender.org` | none | per archive | low–medium |
| I. Git LFS | Yes | yes | no | `lfs.github.com` | GitHub proxy | 10 GiB bandwidth/month | low |
| J. Own S3/R2 bucket | Yes (like B) | yes | yes | `r2.dev` for R2 public | none (public-read) | pay per GB | medium+ |
| K. Remote Control / self-hosted | Yes (native) | yes | yes | n/a | n/a | your hardware | low |

## 7. Recommendation

1. **Option B on top of A, for ty: the main win.**
   - A CI workflow builds the dev `target/` at `/home/user/blender-extension-developer-suite` as root with the
     pinned toolchain, and publishes `ty-target-<ruff-blender commit>.tar.zst` plus a manifest to a rolling
     GitHub release (for example the tag `cache`). It runs on pushes that move the `ty-blender` pointer, and
     uses the Actions cache inside CI to stay incremental itself.
   - A `cache:restore` mise task (`scripts/restore_cache.py`) downloads the asset whose commit matches the
     checkout, or else the newest one. It verifies a checksum, extracts it, backdates the mtimes of files
     unchanged since the cache commit, and runs `ty:build`.
   - The setup script calls it instead of `mise run ty:build`, so the setup finishes within 5 minutes and the
     environment snapshot takes over.
2. **Measure before going further** (open questions 1 and 2). In a second session, check whether the snapshot
   kept the repo checkout and its mtimes, and time `mise run ty:build` with and without the mtime fix. If the
   snapshot re-clones the repo, keep the restored `target/` outside the repo (for example
   `/opt/suite-cache/ruff-target`). A SessionStart hook in `.claude/settings.json`, guarded by
   `CLAUDE_CODE_REMOTE=true` (docs), then re-links it and redoes the mtime fix in every session. That hook is
   also where the submodule initialisation has to go, since a cached environment skips the setup script.
3. **Blender: ship outputs, not the build (option H as the fallback).** Publish the `main` build's
   `blender-bin`, `bpy-rst` and `bpy-stubs*` keyed by the Blender commit, so every check task works without a
   Blender build. Admittedly this does not meet the incremental requirement for Blender C/C++ edits.
   - For those edits, use Remote Control on your own machine (K), where the incremental build is native.
   - If C/C++ edits in the cloud become common, add ccache (F), which only partly meets the requirement.
4. **Don't pursue** sccache for ty (E), Actions artifacts or cache from the session (D), or LFS (I).

## 8. Open questions (unverified)

1. How long does `ty:build` take on a restored `target/` whose sources all have fresh mtimes (no mtime fix)?
   rustc reuses `incremental/`, but the cost of rerunning ~40 crates is unknown. Measure it with
   `mise run ty:build` after `touch`ing the sources.
2. Does the environment snapshot keep the repository checkout, including the ignored `target/` and the
   initialised submodules, and how is a new session's branch checked out into it (a fresh clone, or a
   fetch/checkout in place, which would keep mtimes)? The docs only say "snapshots the filesystem".
3. How long does a ccache replay build of Blender take on 4 vCPU, and how big is a ccache for a Release `full`
   build? How big are `.cache/blender-build/main`, `.cache/blender-libs/linux_x64` and the install dir? None
   were measured: no Blender build exists in this container.
4. Does a full Blender build fit a 14 GB GitHub runner SSD and 6 hours? A `lite` or `headless` config
   (`--config`, `mise.toml` `blender:build`) might.
5. Is rustc's incremental cache reused from a different absolute path? It is avoided here by building at the
   same path.
6. Would `SUITE_JOBS=4` in the setup script bring today's clean ty build under the 5-minute window on its own?
7. Does `*.r2.cloudflarestorage.com` really pass the proxy for a real account endpoint? Docker Hub pulls were
   not tested either.
