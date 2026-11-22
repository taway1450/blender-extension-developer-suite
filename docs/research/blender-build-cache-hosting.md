# Caching the Blender build for cloud sessions: approaches and hosts

Research note, 2026-11-22. This note follows up
[cloud-session-build-cache.md](cloud-session-build-cache.md), which covered ty and Blender together. It
looks only at Blender, because Blender's build takes much longer and so gains the most from a cache. It asks
two things:

1. Which ways of caching Blender's C/C++ build exist, and how do they compare?
2. Where can the cache live, ideally for free, including on your own computer?

**The hard requirement.** After a cloud session restores the cache, you edit Blender's C/C++ source and run
`mise run blender:build main` again. That run must rebuild only what changed, not everything.

Every fact has a source next to it: a URL, a `path:line` in this repo or its `blender` submodule, or a
command run in this cloud session (*verified locally*, 2026-11-22). Estimates are labelled **estimate**. My
own advice is kept to [section 7](#7-recommendation), apart from verdicts in the text marked
**Recommendation**. Nothing was built for this note.

---

## 1. Summary

- **Only one approach meets the hard requirement on the first build after a restore: restore the build
  directory and repair the source mtimes.** Ninja compares mtimes and command lines, not content
  (section 3.1), and a restored build directory keeps both. Before the build, the worktree and `lib/` must
  be checked out so that only files that really differ from the cache's commit get a new mtime
  (section 3.3).
- **ccache alone does not meet the requirement on its own.** It survives a fresh checkout because it
  hashes content. But without a build directory, the first `blender:build` still configures CMake, runs
  every compile (as cache hits) and every link. That build is a replay, not an incremental rebuild
  (section 3.2). ccache works best as a safety net next to the restored build directory.
- **`blender:build` currently ignores uncommitted edits.** It skips the build whenever
  `.cache/blender-bin/<name>/.build-info` names the same commit, config and build type
  (`scripts/build_blender.py:175-183`). The only way around that is `--force`, which deletes the build
  directory. So editing C/C++ in the worktree and rerunning the task does nothing today, cache or no
  cache. The script has to change for the requirement to hold at all (section 3.5).
- **Host: GitHub Releases on this public repo is free, needs no secret, and is on the default
  allowlist.** The 2 GiB limit per asset means splitting the archive. A free GitHub Actions job on
  `ubuntu-24.04` (4 vCPU, 16 GB RAM, 6 h per job) can produce the cache. Every other object store tested is
  either blocked by this session's proxy or, for S3 and R2, signs its requests in a way that a
  header-injecting network secret cannot provide (section 5).
- **ccache's remote storage is usable from a cloud session only over HTTPS, through a storage helper.**
  Built-in `http://` is plain HTTP, and `redis://` is plain TCP. The proxy allows only HTTPS `CONNECT`
  on port 443 (*verified locally*). Of ccache's two official HTTPS helpers, the C++ one (libcurl) follows
  `HTTPS_PROXY`. The Go one builds its own `http.Transport` without a proxy setting, so it would ignore
  the proxy (section 4.2).
- **The precompiled libraries for `linux_x64` are about 2.5 GB** at the commit the submodule pins: 2.22 GB
  of git LFS objects plus about 248 MB of regular files (*verified locally*). They download from
  `projects.blender.org`, which this environment already allows, at about 14 MB/s (*verified locally*). So
  they do not need to be re-hosted.

## 2. What exactly gets built

- **Ref.** `blender:build <name>` creates the worktree `.cache/blender-src/<name>` from the `blender`
  submodule at `<ref>` (default: the name itself), with `GIT_LFS_SKIP_SMUDGE=1`
  (`scripts/generate_stubs.py:111-142`). The build then runs `git lfs pull` in it
  (`scripts/build_blender.py:191`). The submodule points at the fork `projects.blender.org/Simon-Sak/blender`
  (`.gitmodules`), whose C/C++ differs from upstream in hundreds of files
  ([cloud-session-build-cache.md, 2.2](cloud-session-build-cache.md#22-blender-from-source-blenderbuild)).
  So upstream's daily builds are not a substitute.
- **Configure and build.** CMake with `-G Ninja`, `-C build_files/cmake/config/blender_<config>.cmake`
  (default `full`), `CMAKE_BUILD_TYPE=Release`, an absolute `LIBDIR` and an absolute `CMAKE_INSTALL_PREFIX`.
  The build dir is `.cache/blender-build/<name>`, and `cmake --build … --target install` installs into
  `.cache/blender-bin/<name>` (`scripts/build_blender.py:195-232`). CMake and Ninja come from PyPI through
  the script's inline dependencies, `cmake>=3.21` and `ninja`, which are not pinned
  (`scripts/build_blender.py:1-4`).
- **Parallelism.** `CMAKE_BUILD_PARALLEL_LEVEL` defaults to half the logical CPUs
  (`scripts/_resources.py:29-35`). On the 4-vCPU cloud VM that is **2 jobs** (`nproc` = 4, *verified
  locally*; [cloud-environments#resource-limits](https://code.claude.com/docs/en/cloud-environments#resource-limits)).
  `SUITE_JOBS` overrides it.
- **Precompiled libraries.** `ensure_libraries` clones `https://projects.blender.org/blender/lib-linux_x64.git`
  with `--filter=blob:none` into `.cache/blender-libs/linux_x64`, checks out the pinned commit and runs
  `git lfs pull` (`scripts/build_blender.py:71-107`). The submodule pins `lib/linux_x64` at `bd0e2baa`
  (`git ls-tree HEAD lib/` in `blender/`, *verified locally*).
  - **Size at that commit** (*verified locally*: a shallow `GIT_LFS_SKIP_SMUDGE=1` fetch, then
    `git lfs ls-files -s`): 716 LFS files totalling 2.22 GB, of which `dpcpp` is 0.85 GB, `llvm` 0.37 GB and
    `python` 0.35 GB. On top of that come 15,039 tree entries of regular blobs totalling 248 MB. The
    server-side size of the whole repository, history included, is 26.2 GB (`size` field of
    `GET https://projects.blender.org/api/v1/repos/blender/lib-linux_x64`).
  - **git-lfs keeps a second copy.** git-lfs stores downloaded objects under `.git/lfs/objects`
    (`LocalMediaDir` in `git lfs env`, *verified locally*) in addition to the checked-out files. So the
    shared clone takes about 4.5 GB of disk.
  - **Download path and speed.** The LFS batch API answers with a download `href` on
    `projects.blender.org` itself. An 84 MB object (`python/lib/libpython3.13.a`) came down at 14.3 MB/s
    (*verified locally*). That puts the 2.22 GB at about 2.6 minutes.
- **Features that matter for caching** (all in `blender/CMakeLists.txt`):
  - `WITH_UNITY_BUILD` is ON by default (lines 247-259), and seven targets use it, such as
    `bf_nodes_geometry` (`source/blender/nodes/geometry/CMakeLists.txt:435`).
  - `WITH_COMPILER_PRECOMPILED_HEADERS` is ON (lines 261-282). `bf_io_usd` and `bf_freestyle` use PCH
    (`source/blender/io/usd/CMakeLists.txt:232-233`, `source/blender/freestyle/CMakeLists.txt:580-581`).
  - `WITH_COMPILER_CCACHE` is OFF by default (lines 1247-1254). When ON, it sets
    `CMAKE_C(XX)_COMPILER_LAUNCHER` to the absolute path of `ccache`
    (`build_files/cmake/platform/platform_unix.cmake:1109-1123`).
  - `WITH_LINKER_LLD` and `WITH_LINKER_MOLD` are ON (lines 1012-1014).
  - `blender_full.cmake` sets `WITH_BUILDINFO ON`. `buildinfo.h` is regenerated on every build with the
    current `BUILD_TIME` (`source/creator/CMakeLists.txt:257-273`, `build_files/cmake/buildinfo.cmake:179-194`).
    So every `ninja` run recompiles the build-info source and relinks `blender`, unless
    `BUILDINFO_OVERRIDE_DATE`/`_TIME` are set.
- **Translation units.** There are 4,866 `.c`/`.cc`/`.cpp` files under `source/`, `intern/` and `extern/`,
  4,468 of them outside test paths (*verified locally*, `find`). Unity builds merge some of them, so the
  number of compile jobs is lower. The source tree without `.git` is 365 MB.
- **Blender's own numbers.** Blender asks for at least 16 GB of ccache, recommends 32 GB, and notes that "a
  debug ASAN build on Linux can approach 4GB"
  (`build_files/cmake/compiler_ccache_max_size_check.cmake:10-18`). Blender's docs recommend
  `make ccache ninja` on Linux and macOS. sccache is documented for Windows and Ninja only
  ([options.md](https://projects.blender.org/blender/blender-developer-docs/raw/branch/main/docs/handbook/building_blender/options.md),
  "Debug Builds").

## 3. Approaches

### 3.1 How Ninja decides what to rebuild (the core constraint)

Source: `src/graph.cc` at ninja `a00b184`
([graph.cc](https://github.com/ninja-build/ninja/blob/a00b184d0cc3658ce2f5d2a81c7d86569d950b57/src/graph.cc)),
`RecomputeOutputDirty`, roughly lines 223-285.

- An output is dirty if it is missing, or if "output … older than most recent input"
  (`output->mtime() < most_recent_input->mtime()`).
- It is dirty if the "command line changed": the hash of the command differs from the one in `.ninja_log`.
- It is dirty if the "recorded mtime of … [is] older than most recent input", where the mtime comes from
  `.ninja_log`.
- It is dirty if the "command line [is] not found in log". So a build directory without its `.ninja_log`
  rebuilds everything.
- The ninja manual says Ninja "runs whichever commands are necessary … as determined by file modification
  times" ([manual](https://github.com/ninja-build/ninja/blob/master/doc/manual.asciidoc), "Conceptual
  overview"). It also keeps a log of each output's command in `.ninja_log` ("The Ninja log"). Header
  dependencies go into `.ninja_deps`.
- **Consequences for a restored build directory:**
  1. `.ninja_log` and `.ninja_deps` must come with it.
  2. Every compile command must be byte-identical. That covers the absolute paths of sources, include
     directories and the compiler, and the ccache launcher path, if one is used.
  3. Every source file, header and library that did not change must have an mtime older than the outputs
     and than the mtimes recorded in the log.
- **CMake also pins the source directory.** If `CMakeCache.txt`'s `CMAKE_HOME_DIRECTORY` is not the same
  file as the current source dir, CMake stops with "does not match the source … used to generate cache"
  (`Source/cmake.cxx:2397-2409` at CMake `9ea74a5`,
  [cmake.cxx](https://github.com/Kitware/CMake/blob/9ea74a5b2b4300cb274d0b47d7b8901446bb5d77/Source/cmake.cxx)).
  All four paths `build_blender.py` passes are absolute (`scripts/build_blender.py:199-213`). So a restored
  build directory only works at the identical absolute path:
  `/home/user/blender-extension-developer-suite/.cache/…`. The cloud checkout is always at that path
  ([cloud-session-build-cache.md, 3.1](cloud-session-build-cache.md#31-cargo-the-target-dir-survives-a-move-but-not-new-mtimes)).

### 3.2 ccache

All quotes come from the v4.14.3 manual, released 2026-11-08
([manual.adoc](https://github.com/ccache/ccache/blob/v4.14.3/doc/manual.adoc),
[news.adoc](https://github.com/ccache/ccache/blob/v4.14.3/doc/news.adoc)).

- **Hashing.**
  - *Direct mode* (default on) hashes "the input source file" and "the compiler options". It then looks
    up a manifest holding the include files' paths and hashes, and compares them with the current
    contents.
  - *Preprocessor mode* hashes the `-E` output. Direct mode falls back to it on a miss.
  - *Depend mode* "will not use the preprocessor at all". It gets the includes from `-MD`/`-MMD` output.
    Misses are cheaper, but "the cache hit rate will likely be lower" (sections "How ccache works",
    "The direct mode", "The depend mode").
  - All modes hash "the compiler's size and modification time" by default (`compiler_check = mtime`).
    `compiler_check = content` or a command string such as `%compiler% -v` is more robust across
    machines (section `compiler_check`).
- **It survives a fresh checkout.** The key is content, not mtimes. The one mtime rule: when a source or
  include file's mtime or ctime "is equal to (or newer than) the time that ccache was invoked, ccache
  disables caching completely". Files checked out seconds before the build are therefore fine. Setting
  `sloppiness = include_file_mtime,include_file_ctime` opts out of this check entirely (section "Handling
  of newly created source files").
- **Different checkout paths.** `base_dir` "converts absolute paths to relative paths … but only for
  paths that start with one of the specified base directories" (section `base_dir`). `hash_dir` (default
  true) puts the working directory in the hash only "when generating debug info (`-g`)", unless
  `-fdebug-prefix-map`/`-fdebug-compilation-dir` is used (section `hash_dir`). The default `Release` build
  has no `-g`. `RelWithDebInfo` would need one of those flags or `hash_dir = false`.
- **Sloppiness that matters here:**
  - PCH support needs `sloppiness = pch_defines,time_macros`. With GCC, PCH also needs `-include`
    (CMake's PCH uses that) and `-fpch-preprocess`. "Without proper setup, ccache falls back to the
    non-precompiled header" (section "Precompiled headers"). So the two PCH targets (section 2) may not
    get cached without that setup.
  - `time_macros` makes ccache ignore `__DATE__`/`__TIME__`. Direct mode is disabled when "the string
    `__TIME__` is present in the source code" ("The direct mode").
  - `system_headers` stops tracking system headers. It helps when OS versions differ (sections
    `sloppiness` and "Sharing a cache on NFS").
- **Unity builds.** CMake generates `unity_*.cxx` files in the build directory that `#include` the real
  sources. ccache treats each as one source file plus includes. That works, but one edited source
  invalidates its whole unity batch (by how unity builds work; Blender's
  [unity_builds.md](https://projects.blender.org/blender/blender-developer-docs/raw/branch/main/docs/handbook/tooling/unity_builds.md)
  describes the merging).
- **Size and compression.** `max_size` defaults to 5 GiB. Compression is on by default, using Zstandard
  at level 1 (sections `max_size`, `compression`, `compression_level`). For Blender: at least 16 GB
  configured (section 2). **Estimate:** a single Release `full` configuration fills well under that, likely
  2–5 GB compressed. Debug ASAN reaches about 4 GB, and Release objects have no debug info. Not measured.
- **Remote storage.**
  - `remote_storage` lists backends queried "after checking the local cache (unless `remote_only` is
    true)".
  - Local miss, remote hit: "Read from remote, write to local". Miss on both: "Compile, write to local,
    write to remote", unless `read-only=true`.
  - With `remote_only`: "Read from remote, don't write to local" (section "Storage interaction").
  - Remote storage holds individual entries: results and manifests, keyed by hash. **So ccache fetches
    only the entries a compile asks for, never the whole cache.** Each direct-mode hit costs about one
    manifest read plus one result read (from the manifest description in "The direct mode"; my reading,
    not measured).
  - Built-in backends: `file:` (a directory, e.g. NFS; `@layout=local` reads a copied local cache
    read-only, added in 4.14) and `crsh:`.
  - "All other schemes require a storage helper program", named `ccache-storage-<scheme>` (section
    "Remote storage backends").
  - Built-in `http://` and `redis://` are deprecated in 4.14 and "will be removed in the next non-bug-fix
    ccache version". The HTTP backend states "HTTPS is not supported" (news.adoc lines 190-200; manual
    "HTTP storage backend").
  - Helpers arrived in 4.13 (2026-03-05). Ubuntu 24.04 ships ccache 4.9.1
    ([packages.ubuntu.com/noble/ccache](https://packages.ubuntu.com/noble/ccache)), which has no helpers.
    The upstream binary `ccache-4.14.3-linux-x86_64-glibc.tar.xz` downloads from GitHub Releases (HTTP 200,
    *verified locally*).
- **Official helpers.**
  - [ccache-storage-http-cpp](https://github.com/ccache/ccache-storage-http-cpp) and
    [ccache-storage-http-go](https://github.com/ccache/ccache-storage-http-go) handle HTTP and HTTPS. They
    support `@bearer-token`/`@bearer-token-file`, custom `@header`, netrc and the layouts
    `subdirs`/`flat`/`bazel` (both READMEs).
  - [ccache-storage-redis](https://github.com/ccache/ccache-storage-redis) handles `redis://` and
    `rediss://`.
  - The helper protocol is in
    [remote_storage_helper_spec.md](https://github.com/ccache/ccache/blob/v4.14.3/doc/remote_storage_helper_spec.md).
- **Server side.**
  - "Any simple HTTP server can be used read-only." Read-write needs `PUT` and maybe `DELETE`, for example
    nginx with `dav_methods PUT DELETE; create_full_put_path on;`, or `bazel-remote` with
    `--disable_http_ac_validation` and `layout=bazel`
    ([ccache wiki, HTTP storage](https://github.com/ccache/ccache/wiki/HTTP-storage)).
  - bazel-remote needs `--max_size` (it evicts by LRU) and supports `--htpasswd_file`
    ([bazel-remote README](https://github.com/buchgr/bazel-remote/blob/master/README.md)).
- **Incremental?** Partly. ccache makes recompiles cheap but does not stop them. With a fresh build
  directory, every compile runs through ccache and every link runs for real. Only after that replay is
  Ninja incremental again
  ([cloud-session-build-cache.md, 3.3](cloud-session-build-cache.md#33-ninja-and-ccache-blender)).

### 3.3 Restoring the build directory, plus the mtime repair

- **What to restore** (same absolute paths, mtimes preserved, which tar does by default):
  - `.cache/blender-build/<name>` (with `.ninja_log`, `.ninja_deps`, `CMakeCache.txt`,
    `configure-args.txt`)
  - `.cache/blender-bin/<name>` (with `.build-info`)
- **Re-creating the sources so that only real changes look new.**
  1. Check out the worktree, and the `lib/linux_x64` clone, at the **cache's** commits.
  2. Set every file's mtime to a fixed time T0 before the cache build started.
  3. Then `git checkout` the commit you actually want. git rewrites only the files that differ, so
     exactly those get a new mtime.
  4. Uncommitted edits made afterwards get new mtimes as usual.

  This follows from Ninja's rules (3.1). It avoids a trap that the commit-time tools fall into:
  `git-restore-mtime`, or setting every file to its commit time, can backdate a file that changed after
  the cache's commit to a time *before* the cache was built. Ninja would then skip it. (My reasoning from
  the rules in 3.1, not tested.)
- **What else has to match:**
  - The compiler and system headers. Ninja tracks `/usr/include` headers through `.ninja_deps`, so the
    CI image must carry the same apt package versions as the cloud image: Ubuntu 24.04, GCC 13.3.0
    (`gcc --version`, *verified locally*;
    [cloud-environments](https://code.claude.com/docs/en/cloud-environments), "Ubuntu 24.04 on x86_64").
  - The ccache launcher path baked into `CMakeCache.txt`, if ccache was on.
  - `configure-args.txt`, which `build_blender.py` compares byte for byte. It contains the absolute paths
    of the `uv`-provided `cmake` and `ninja` (`scripts/build_blender.py:198-228`). If they differ, the
    script deletes `CMakeCache.txt` and reconfigures. That does not by itself dirty the objects, unless
    the regenerated commands differ (3.1). But the unpinned `cmake>=3.21`/`ninja` deps make that more
    likely (open question 3).
- **Incremental?** **Yes.** This is the only approach where the first build after a restore recompiles
  just the changed files and relinks (plus the build-info relink, section 2).
- **What breaks it:**
  - A different absolute path: CMake refuses (3.1).
  - Different compile commands, a missing `.ninja_log`, or blanket "now" mtimes: full rebuild.
  - A newer system header: a correct but large rebuild.
- **Size.** Not measured. **Estimate:** a Release `full` build directory of several GB (objects without
  debug info, static libraries per module, the Cycles kernels), roughly 1.5–3 GB with `zstd`. Plus the
  install dir, about 1 GB. Without splitting, that does not fit one 2 GiB release asset.

### 3.4 sccache (for comparison)

Source: sccache v0.19.0 ([README](https://github.com/mozilla/sccache/blob/v0.19.0/README.md), [docs/](https://github.com/mozilla/sccache/tree/v0.19.0/docs)).

- **Backends:** local disk, S3, R2, Redis, Memcached, GCS, Azure, GitHub Actions, WebDAV ("Ccache/Bazel/Gradle
  compatible"), Alibaba OSS, Tencent COS, and multi-level combinations (README, "Storage Options";
  `docs/MultiLevel.md`).
- **Key differences for Blender:**
  - **Preprocessor cache mode** (sccache's equivalent of ccache's direct mode) "will be disabled" when
    "Not using local storage for the cache" (`docs/Local.md:22-28`). With a remote-only backend, every
    hit runs the preprocessor, which is expensive for Blender's template-heavy C++. ccache's direct mode
    works with remote storage.
  - Paths: "By default, absolute paths to files must match". `SCCACHE_BASEDIRS` works like ccache's
    `base_dir` (README, "Normalizing Paths").
  - **S3 and R2** need `SCCACHE_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com` and signing
    credentials. `SCCACHE_S3_NO_CREDENTIALS` gives "public readonly access" (`docs/S3.md:24-42`).
  - **WebDAV** takes `SCCACHE_WEBDAV_TOKEN` (bearer) or a username and password, so a proxy-injected
    `Authorization` header could stand in (`docs/Webdav.md`, "Credentials").
  - HTTPS goes through reqwest with the platform verifier (`src/util.rs`, `new_reqwest_client_builder`),
    which should trust this VM's system store, which holds the proxy CA (`/root/.ccr/README.md`). Not
    tested.
  - sccache runs as a server daemon. "The local storage only supports a single sccache server at a time"
    (`docs/Local.md`).
- **Blender's stance:** sccache only on Windows with Ninja (`WITH_WINDOWS_SCCACHE`,
  `blender/CMakeLists.txt:1215`; options.md).
- **Verdict.** For Linux Blender builds, ccache is the better fit: Blender supports it on Linux, direct
  mode works with remote storage, and there is no server process. sccache wins only if you want its
  native S3/R2/GCS clients, and those need signing credentials (section 5).

### 3.5 What `blender:build` must change for any cache to be incremental

- `build_blender` returns early when `blender` exists and `.build-info` starts with the same
  `commit=…\nconfig=…\nbuild_type=…` (`scripts/build_blender.py:175-183`). An uncommitted edit in
  `.cache/blender-src/main` leaves HEAD unchanged, so the edit is never compiled.
- `--force` deletes the whole build directory (`scripts/build_blender.py:195-198`), which is the opposite
  of incremental.
- **Recommendation.** Skip the build only when the worktree is also clean (`git status --porcelain`). Or
  always run `cmake --build`: a Ninja no-op is cheap, apart from the build-info relink, which
  `BUILDINFO_OVERRIDE_DATE`/`_TIME` can remove (section 2).

### 3.6 Combinations, lighter builds, and other options

- **Build directory plus ccache.**
  - The build directory gives the true incremental build.
  - ccache covers what Ninja recompiles anyway: a cache older than HEAD, a reconfigure, a header touched
    by mistake. For those, the cache's objects are hits.
  - Both come from the same CI job.
- **Final outputs as the fallback.** Most sessions only need Blender's outputs, not a build tree: the
  binary, `bpy-rst` and the stubs
  ([cloud-session-build-cache.md, option H](cloud-session-build-cache.md#h-blender-daily-builds-builderblenderorg-or-a-final-blender-archive)).
  An archive of `.cache/blender-bin/main` with its `.build-info` lets `build_blender` short-circuit
  (`scripts/build_blender.py:175-183`).
- **Lighter presets.**
  - `blender_lite.cmake` turns off Cycles, Freestyle, USD, Alembic, FFmpeg, OpenVDB, OIDN and more.
  - `blender_headless.cmake` sets `WITH_HEADLESS` and turns off audio and some input.
  - `bpy_module.cmake` builds Blender as a Python module.
  - All three are in `blender/build_files/cmake/config/`.

  Lite builds much less. But lite removes modules that register Python API (for example Cycles and
  Freestyle), so stubs from a lite build would differ from `main`'s baselines (my reading of the preset).
  Whether headless changes the API surface is not checked (open question 5).
- **Dropping the libraries from the cache.** They are pinned per Blender commit (2.5 GB, section 2) and
  already come from `projects.blender.org` at about 14 MB/s. They don't need re-hosting, only the same
  mtime treatment as the sources (3.3).
- **distcc / icecream to your own machine.** distcc talks TCP on its own port. The Blender docs say that
  for "incremental rebuilds and general development, there aren't significant advantages to distributing"
  ([distcc.md](https://projects.blender.org/blender/blender-developer-docs/raw/branch/main/docs/handbook/tooling/distcc.md)).
  This proxy allows only HTTPS `CONNECT` to port 443. Ports 6379 and 8443 were reset, and plain `http://`
  has no route because there is no DNS and no `HTTP_PROXY` (*verified locally*). It also re-terminates TLS
  (`/root/.ccr/README.md`). **Not viable** without an HTTP-tunnelling layer.
- **Bazel-style remote caches** (Bazel, Buck, BuildBuddy) cache actions of their own build graph. Blender
  builds with CMake, so they do not apply. The one useful overlap: a `bazel-remote` server can act as
  ccache's HTTP backend (`layout=bazel`, 3.2).
- **Not caching at all: Remote Control.** A session on your own computer keeps `.cache/` between sessions,
  so the build is natively incremental. Cloud sessions are fresh VMs. Remote Control "sessions run directly
  on your machine" and are available on Pro, Max, Ultra, Team and Enterprise plans
  ([remote-control](https://code.claude.com/docs/en/remote-control.md), overview and requirements). This
  session has no computer folders registered (`list_computer_folders` returned none, *verified locally*).

## 4. Constraints from the cloud session

### 4.1 Platform facts (Claude Code docs, [cloud-environments](https://code.claude.com/docs/en/cloud-environments.md))

- **The VM.** Ubuntu 24.04 on x86_64, 4 vCPUs, 16 GB RAM, 30 GB disk ("Resource limits"). 24 GB of disk
  were free in this session (`df`, *verified locally*).
- **The environment snapshot.** It forms only "when setup completes within roughly five minutes". It is
  rebuilt when the setup script or allowed hosts change, or "after roughly seven days" ("Environment
  caching").
- **Network secrets** are headers that the agent proxy adds for the hosts you list. Those hosts then
  bypass the allowlist. The proxy never adds them to "Setup script requests", GitHub, the Anthropic API or
  the package registries ("Add network secrets", "Requests that never get the secret").
  - The form offers a Bearer `Authorization` header, a custom header name, or username and password
    ("Add a secret"; the `request_credential` tool's options).
  - **So:** the setup script can only download anonymously. A build that runs later in the session (a
    ccache helper, `curl` in a SessionStart hook) does get the injected header.
  - A static header cannot do AWS SigV4 or short-lived OAuth. A Google Drive OAuth access token lasts
    one hour (Google OAuth docs, not fetched here; widely documented), so it cannot be a static header.
- **No custom base image.** "Replacing the base image entirely isn't supported yet." ("Installed tools" /
  custom image note.)

### 4.2 What the proxy lets through (*verified locally*, `curl` through the session proxy)

| Host | Result here | Notes |
| --- | --- | --- |
| `github.com`, `release-assets.githubusercontent.com`, `objects.githubusercontent.com` | reachable | release asset downloads work (sccache v0.19.0, ccache 4.14.3 tarballs: 200) |
| `ghcr.io` | reachable | blobs redirect to `pkg-containers.githubusercontent.com`: **blocked** (403) |
| `registry-1.docker.io`, `auth.docker.io`, `production.cloudfront.docker.com` | reachable | a full anonymous pull of an `alpine` layer worked |
| `*.amazonaws.com` (S3) | reachable | `s3.us-east-1.amazonaws.com` 405/307, bucket hosts 403/301 from AWS |
| `<32-hex>.r2.cloudflarestorage.com` | `CONNECT` **allowed** (200) | TLS failed upstream for a made-up account ID; not tested with a real account |
| `pub-*.r2.dev`, `*.workers.dev` | **blocked** (403) | |
| `storage.googleapis.com`, `www.googleapis.com`, `oauth2.googleapis.com` | reachable | Drive API answered "The request is missing a valid API key." |
| `drive.google.com`, `drive.usercontent.google.com` | **blocked** | |
| `huggingface.co`, `cdn-lfs*.hf.co`, `cas-bridge.xethub.hf.co`, `cas-server.xethub.hf.co` | **blocked** | |
| Backblaze (`s3.us-west-004.backblazeb2.com`, `f004.backblazeb2.com`, `api.backblazeb2.com`) | **blocked** | |
| Wasabi, Oracle Object Storage, Hetzner (`*.your-objectstorage.com`, `*.your-storagebox.de`), Storj, Tigris (`fly.storage.tigris.dev`, `t3.storage.dev`), iDrive e2 | **blocked** | |
| Dropbox, OneDrive/Graph, Mega, `archive.org` | **blocked** | |
| `downloads.sourceforge.net` | reachable (404) | `frs.sourceforge.net` reset |
| `*.trycloudflare.com`, `*.ngrok-free.app`, `*.ngrok.app`, `*.ts.net` | **blocked** | |
| `projects.blender.org` | reachable (this environment allows it) | LFS objects served from it, 14.3 MB/s |
| `ccache.dev` | **blocked** | docs mirrored in the GitHub repo |
| Non-443 ports, plain `http://` | **no route** | 6379/8443 reset; no DNS for plain HTTP |

- The default allowlist includes `*.amazonaws.com`, `*.r2.cloudflarestorage.com`, `*.googleapis.com`,
  `storage.googleapis.com`, Docker Hub and the GitHub hosts
  ([cloud-environments#default-allowed-domains](https://code.claude.com/docs/en/cloud-environments#default-allowed-domains)).
- A blocked host can be added under the environment's Allowed domains. Adding one also invalidates the
  environment snapshot once (same page, "Environment caching").
- **Latency.** Each request takes about 60–130 ms once connected, and a new TLS connection costs
  0.13–0.35 s (`curl -w` timings to GCS and S3, *verified locally*). A single stream reached about
  16 MB/s from GCS, 14 MB/s from `projects.blender.org` and about 21 MB/s from GitHub Releases (*verified
  locally*; the GitHub figure is from
  [cloud-session-build-cache.md](cloud-session-build-cache.md#b-ci-builds-target-published-as-a-github-release-asset-and-restored-in-setup-combined-with-a)).
- **ccache helpers and the proxy.**
  - The C++ helper uses libcurl, sets no `CURLOPT_PROXY`, and reads `SSL_CERT_FILE`/`SSL_CERT_DIR` into
    `CURLOPT_CAINFO`/`CAPATH` (`src/storage_client.cpp:364-409`, `src/config.cpp:72-79` at `3f3346a`).
    libcurl honours `https_proxy` from the environment by default, and this VM sets `SSL_CERT_FILE` to the
    proxy CA (`env`, *verified locally*). **It should work through the proxy.**
  - The Go helper builds `&http.Transport{…}` without a `Proxy` field (`storage_client.go:71-80` at
    `00815bb`). In Go, that means no proxy, and there is no DNS for direct connections here. **It would
    fail** unless patched. Not run.
  - The C++ helper has no prebuilt binaries: its README only documents building from source with
    libcurl, libuv and Meson or CMake.

### 4.3 Remote fetch versus whole-archive download (estimates from the numbers above)

- **Remote, per entry.** About 4,000+ compile jobs × ~2 GETs × ~60–130 ms, divided by 2 parallel jobs,
  comes to roughly **4–9 minutes of request latency** in a replay build. On top of that come the local
  hashing and every link. The helper keeps up to 32 connections alive, but Ninja runs only 2 compiles at
  once (section 2). **Estimate.**
- **Whole archive.** A 2–5 GB ccache dir at 14–21 MB/s takes roughly **2–6 minutes**, then all hits are
  local. **Estimate.**
- **Takeaway.** Remote per-entry storage pays off when a session needs a small part of a large cache, or
  when sessions should write new entries back (`PUT` with an injected auth header). For "restore the CI
  build", one archive is faster and simpler.

## 5. Where to host it

Free-tier figures are from each provider's pricing page or docs, as cited. Some third-party summaries
disagree with each other, so prices should be checked before you buy.

### 5.1 GitHub

- **Releases.**
  - "Each file included in a release must be under 2 GiB". There is no limit on total size or bandwidth
    (github/docs `about-releases.md`, cited in
    [cloud-session-build-cache.md, option B](cloud-session-build-cache.md#b-ci-builds-target-published-as-a-github-release-asset-and-restored-in-setup-combined-with-a)).
  - The repo is public, so downloads need no token, which suits the setup script (same note).
  - The hosts are on the default allowlist and were reachable (4.2).
  - Upload from CI with `GITHUB_TOKEN`.
  - Releases are not an HTTP key-value store for ccache: no `PUT` per key.
- **ghcr.io via oras.** Blobs come from `pkg-containers.githubusercontent.com`, which is blocked (4.2).
  It would have to be allowlisted.
- **Docker Hub as an OCI artifact store.** Pulls work through the proxy (4.2). The documented pull limits
  are 100 per 6 h per IPv4 address for unauthenticated users and 200 per 6 h for Personal accounts
  ([Docker Hub pull usage and limits](https://docs.docker.com/docker-hub/usage/pulls/)). Cloud sessions
  leave through shared proxy IPs, so the anonymous limit may be shared (not verified).
- **Actions cache and artifacts.** These are not readable from a session: Azure blob hosts are blocked,
  and the runtime token exists only in a workflow
  ([cloud-session-build-cache.md, option D](cloud-session-build-cache.md#d-github-actions-artifacts-or-the-actions-cache-read-directly)).
  They are useful only inside the CI job, for example through `hendrikmuhs/ccache-action`, which builds on
  `actions/cache`. The cache holds 10 GB per repo and evicts entries after 7 days unused (same note).

### 5.2 Object storage

- **Cloudflare R2.**
  - Free: 10 GB-month, 1 M Class A and 10 M Class B operations a month, and no egress fees. Beyond that,
    $0.015/GB-month
    ([r2/pricing.mdx](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/r2/pricing.mdx)).
    5 GiB per single-part upload ([r2/platform/limits.mdx](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/r2/platform/limits.mdx)).
  - Public `r2.dev` URLs are "rate-limited and should only be used for development"
    ([public-buckets.mdx](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/r2/buckets/public-buckets.mdx)),
    and they are blocked here.
  - The S3 endpoint `<account>.r2.cloudflarestorage.com` is on the default allowlist, but it needs
    SigV4-signed requests. Two ways to avoid putting the key in the VM:
    - **Presigned URLs**, valid from 1 s to 7 days
      ([presigned-urls.mdx](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/r2/api/s3/presigned-urls.mdx)).
      CI could write fresh presigned GET URLs into a public manifest on GitHub Releases. The setup script
      would then fetch R2 objects with no secret (my design, untested).
    - **A Worker** on a custom domain that accepts `GET`/`PUT` with a bearer token. That token fits a
      network secret, and the Worker would be a ccache HTTP backend. Workers Free allows 100,000
      requests a day and 100 MB request bodies on a free zone
      ([workers/platform/limits.mdx](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/workers/platform/limits.mdx)).
      `*.workers.dev` is blocked here, so the custom domain must be allowlisted, or listed on the
      network secret.
- **AWS S3.**
  - Accounts created since 2025-07-15 get up to $200 of credits on a 6-month free plan instead of the old
    12-month tier
    ([AWS announcement](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan)).
  - 100 GB/month of data transfer out is free, aggregated across services
    ([AWS Global Network FAQ](https://aws.amazon.com/about-aws/global-infrastructure/global-network/faqs)).
  - A public-read bucket works with no credentials over `*.amazonaws.com`, which is allowlisted. Writes
    need SigV4, from CI only.
- **Google Cloud Storage.**
  - 5 GB-month of US regional Standard storage free
    ([free cloud features](https://docs.cloud.google.com/free/docs/free-cloud-features.md.txt)). The
    egress allowance was not confirmed from an official page.
  - `storage.googleapis.com` is allowlisted and reachable. Public objects download anonymously, and
    `gsutil`/`gcloud` are installed in this image (`/root/.ccr/README.md`).
- **Backblaze B2.** First 10 GB free. Egress is free up to 3× the average stored data, then $0.01/GB
  ([B2 pricing](https://backblaze.com/cloud-storage/pricing)). **Blocked** here.
- **Oracle Cloud Always Free.** 20 GiB of object storage and 10 TB/month outbound
  ([Free Tier resource reference](https://docs.cloud.oracle.com/iaas/Content/FreeTier/resourceref.htm);
  [cloud.oracle.com/free](https://cloud.oracle.com/free)). **Blocked** here
  (`objectstorage.<region>.oraclecloud.com`). Pre-authenticated request URLs would avoid the need for
  secrets (Oracle feature, not checked here).
- **Hetzner.**
  - Storage Box BX11: 1 TB for €3.20/month excl. VAT, with HTTPS/WebDAV on port 443
    ([BX11](https://www.hetzner.com/storage/storage-box/bx11/),
    [WebDAV docs](https://docs.hetzner.com/storage/storage-box/access/access-webdav)). WebDAV with basic
    auth works as a ccache HTTP backend (`PUT`/`GET`) and as sccache WebDAV.
  - Object Storage: €4.99/month including 1 TB of storage and 1 TB of egress
    ([pricing](https://www.hetzner.com/storage/object-storage/pricing/)).
  - Both are **blocked** here and would need allowlisting.
- **Wasabi.** No free tier. It bills a minimum of 1 TB, has a 90-day minimum storage duration, and egress
  is free only up to the amount stored ([pricing FAQ](https://wasabi.com/pricing/faq)). **Blocked**.
- **Storj.** No standing free tier, only a trial. Since 2026-07-01, $7/TB for storage and egress
  ([Storj pricing](https://storj.dev/dcs/pricing/simplified)). **Blocked**.
- **Tigris.** 5 GB a month free, with zero egress fees ([pricing](https://www.tigrisdata.com/pricing.md)).
  **Blocked**.
- **iDrive e2.** "Try with 10 GB Free". Egress is free up to 3× storage, and pay-as-you-go has a $6
  minimum ([e2 pricing](https://www.idrive.com/e2/pricing),
  [pricing policies](https://e2help.idrive.com/hc/en-us/articles/10910766716573-IDrive-e2-pricing-policies)).
  **Blocked**.

### 5.3 Consumer cloud drives

- **Google Drive.**
  - 750 GB per user per 24 h of uploads and copies, and files up to 5 TB
    ([Workspace storage and upload limits](https://support.google.com/a/answer/172541);
    [Drive API usage limits](https://developers.google.com/drive/api/v3/limits)).
  - Free accounts have 15 GB.
  - A heavily downloaded file can be locked with `downloadQuotaExceeded` for about 24 h. Google does not
    document the threshold (rclone forum reports, e.g.
    [#19939](https://forum.rclone.org/t/gdrive-error-403-download-quota-for-this-file-has-been-exceeded/19939)).
  - Service accounts created after 2025-04-15 get no Drive storage, so CI uploads need a user's OAuth
    refresh token or a shared drive
    ([Fivetran troubleshooting](https://fivetran.com/docs/activations/destinations/available-destinations/google-drive/troubleshooting/service-accounts-storage-quota);
    [rclone forum](https://forum.rclone.org/t/google-drive-service-account-changes-and-rclone/50136)).
  - The API host `www.googleapis.com` is reachable (4.2). A public file can be fetched with an API key,
    which could live in an `X-Goog-Api-Key` network secret (static, unlike OAuth tokens). Whether
    `alt=media` redirects to a blocked host was not tested.
  - **Workable for whole archives, fragile, no ccache backend.**
- **Dropbox, OneDrive, Mega.** All **blocked** (4.2). They also offer no anonymous direct API download
  suited to a no-secret setup script.

### 5.4 Not appropriate

- **Hugging Face Hub.** Blocked here (4.2). Free public storage is "best-effort", repos are "generally
  supported up to 300GB", and uploads should be "useful to the community"
  ([storage limits](https://huggingface.co/docs/hub/storage-limits)). A private build cache does not fit
  that.
- **Internet Archive.** Blocked, and it is a public archive meant to keep things permanently, not
  rewritable caches.
- **SourceForge.** File release hosting for open-source projects. Downloads redirect to mirror hosts,
  which would each need allowlisting. Not a fit.

### 5.5 Your own computer

- **ccache server.** nginx WebDAV or `bazel-remote` (3.2), served over HTTPS. Reached from the cloud
  through the C++ HTTPS helper (4.2), with basic or bearer auth in a network secret on that host. A
  network-secret host also bypasses the allowlist (4.1).
- **Exposing it:**
  - **Cloudflare named tunnel** on your own domain: stable hostname, free. Quick tunnels
    (`*.trycloudflare.com`) are "for testing and development" only, capped at "200 in-flight requests",
    have random names, and are blocked here
    ([quick tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)).
  - **Tailscale Funnel**: on all plans, but with "non-configurable bandwidth limits"
    ([Funnel docs](https://tailscale.com/docs/features/tailscale-funnel)). `*.ts.net` is blocked here.
  - **ngrok free**: 1 GB/month outbound
    ([free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)), which is too little.
    Blocked here.
- **Building Blender on your machine and uploading.** This only helps if the build matches the cloud
  exactly (3.3): Linux x86_64, Ubuntu 24.04, GCC 13.3, and the repo at
  `/home/user/blender-extension-developer-suite`. Practically, that means a `ubuntu:24.04` Docker container
  with that bind mount. A Windows or macOS build is useless to the cloud VM.
- **Remote Control** (3.6): no cache needed at all.

### 5.6 Free CI to produce the cache

- **Runner.** Public repos get `ubuntu-24.04` with 4 CPUs, 16 GB RAM and a 14 GB SSD, "free and
  unlimited"
  ([supported-github-runners.md](https://github.com/github/docs/blob/main/data/reusables/actions/supported-github-runners.md)).
  A job may run 6 hours
  ([limits.md](https://github.com/github/docs/blob/main/content/actions/reference/limits.md)). Larger
  runners are billed per minute even for public repos
  ([larger-runners.md](https://github.com/github/docs/blob/main/content/actions/concepts/runners/larger-runners.md)).
- **Disk.** Third-party measurements put the free root space at about 25–29 GB. Removing preinstalled
  software frees up to about 31 GB more
  ([maximize-build-space](https://github.com/easimon/maximize-build-space),
  [free-disk-space](https://github.com/jlumbroso/free-disk-space)).
- **Does a full build fit?** **Estimate:** libraries about 4.5 GB with the LFS copy (section 2), source
  under 1 GB, build directory several GB, ccache 2–5 GB, install about 1 GB. That likely fits after
  freeing disk. Time on 4 cores: a forum data point says about 35 minutes for most of the tree on a
  4-core machine, with tests much longer
  ([devtalk](https://devtalk.blender.org/t/make-debug-developer-takes-forever-to-finish/13611)). Blender's
  buildbot builds Linux in about 30 minutes ([T89125](https://developer.blender.org/T89125)). A cold
  `full` Release build likely fits the 6-hour limit. Not measured.
- **The job has to match the cloud VM.** It must run in an `ubuntu:24.04` container, as root, with the
  checkout at `/home/user/blender-extension-developer-suite` (3.3), and set `SUITE_JOBS=4`.
  `_resources.py` would otherwise use 2 (section 2).

## 6. Comparison

### 6.1 Approaches

| Approach | Incremental on the first build after restore? | Restore cost (cold) | Size (estimate) | Complexity |
| --- | --- | --- | --- | --- |
| **A. Build dir + mtime repair** (3.3) | **Yes**: only changed files recompile, plus relink | download build dir (~1.5–3 GB zst) + libs from blender.org (2.2 GB, ~2.6 min) + checkout | build dir several GB + install ~1 GB | high: same path, same toolchain, exact checkout order, `.build-info` fix |
| **B. ccache, whole cache dir as archive** (3.2) | **No**: one replay build (all compiles as hits, all links), then yes | download 2–5 GB (~2–6 min) + replay build | 2–5 GB | medium: ccache 4.x, `base_dir`, PCH sloppiness |
| **C. ccache remote storage over HTTPS** (3.2, 4.2) | **No**: same replay, plus ~4–9 min of request latency | nothing up front | server holds 2–5 GB+ | medium-high: ccache ≥4.13 + C++ HTTPS helper built from source, an HTTPS server, a network secret |
| **D. sccache remote** (3.4) | **No**: replay, with preprocessing on every hit | nothing up front | similar | medium: signing creds for S3/R2, or WebDAV |
| **A + B** (build dir with ccache as safety net) | **Yes** | A + B downloads | both | highest; most robust |
| **E. Final outputs only** (3.6) | **No**: a C/C++ edit means a full build | ~1 GB | ~1 GB + stubs | low |
| **F. Lighter preset** (lite/headless) | depends on A/B; smaller everything | smaller | smaller | low, but stubs may differ (lite) |
| **G. distcc / icecream** | n/a | n/a | n/a | not viable through the proxy |
| **H. Remote Control on your machine** | **Yes**, natively | none | your disk | low |

### 6.2 Hosts

| Host | Free tier | Beyond free | Auth for a session | Proxy here | Suits |
| --- | --- | --- | --- | --- | --- |
| **GitHub Releases** (public repo) | unlimited size and bandwidth, <2 GiB per file | free | none to read; `GITHUB_TOKEN` in CI to write | **yes** | whole archives (split) |
| ghcr.io (oras) | free for public | — | none to read | **blocked** blob host | archives |
| Docker Hub (oras) | public repos; 100 pulls/6 h anonymous | paid plans | none / Docker login | yes | archives |
| Cloudflare R2 | 10 GB-month, 10 M reads, 1 M writes, zero egress | $0.015/GB-month | SigV4 (presigned URLs or Worker + bearer) | S3 endpoint `CONNECT` ok (untested with an account); `r2.dev`/`workers.dev` blocked | archives; ccache via a Worker; sccache S3 |
| AWS S3 | credits only for new accounts; 100 GB/month egress | ~$0.023/GB-month + egress | public-read, no auth; SigV4 to write | yes | archives; sccache |
| GCS | 5 GB-month US regional | per GB | public objects, no auth | yes | archives; sccache GCS |
| Backblaze B2 | 10 GB, egress free up to 3× stored | ~$6.95/TB-month | S3 SigV4 or B2 token | **blocked** | archives |
| Oracle Always Free | 20 GiB, 10 TB/month egress | — | pre-authenticated URLs | **blocked** | archives |
| Hetzner Storage Box | none | €3.20/month for 1 TB | WebDAV basic auth (fits a network secret) | **blocked** | archives; **ccache HTTP**; sccache WebDAV |
| Hetzner Object Storage | none | €4.99/month incl. 1 TB + 1 TB egress | SigV4 | **blocked** | archives |
| Wasabi / Storj / Tigris / iDrive e2 | none / trial / 5 GB / 10 GB | various | SigV4 | **blocked** | archives |
| Google Drive | 15 GB; 750 GB/day upload | Google One | API key (public file) or 1-h OAuth | API host yes; `drive.google.com` blocked | archives (fragile) |
| Dropbox / OneDrive / Mega | small free tiers | — | OAuth | **blocked** | — |
| Hugging Face / Internet Archive / SourceForge | — | — | — | blocked / blocked / mirrors | not appropriate |
| Your computer via Cloudflare named tunnel | free | your domain (~$10/yr) | basic/bearer in a network secret | must allowlist (or list on the secret) | **ccache HTTP**, archives |
| Your computer via Remote Control | free | — | n/a | n/a | no cache needed |
| GitHub Actions (producer) | free for public repos, 4 vCPU/16 GB/14 GB SSD, 6 h | larger runners billed | — | — | builds the cache |

## 7. Recommendation

This section is my judgement, built on the facts above.

**Primary: CI builds the build directory and ccache; GitHub Releases hosts them; the session restores
on demand (approach A + B).**

1. **Fix `build_blender.py` first** (3.5): build when the worktree is dirty, not only when the commit
   changes. Optionally set `BUILDINFO_OVERRIDE_DATE`/`_TIME` so that a no-op build does not relink.
   Pin `cmake` and `ninja` in the script metadata, so CI and session get the same paths and versions.
2. **Add a CI workflow** on `ubuntu-24.04`, running a `ubuntu:24.04` container as root with the repo at
   `/home/user/blender-extension-developer-suite`:
   - Install ccache 4.14.3 from its release tarball, at the same path the session will use.
   - Configure with `-DWITH_COMPILER_CCACHE=ON`, `CCACHE_BASEDIR=/home/user/blender-extension-developer-suite`,
     `CCACHE_COMPILERCHECK='%compiler% -v'`, `sloppiness=pch_defines,time_macros` and a 16 GB max size.
   - Run `SUITE_JOBS=4 mise run blender:build main`.
   - Tar with `zstd` two archives: `blender-build/main` + `blender-bin/main` (build dir, mtimes kept), and
     the ccache dir. Add a manifest: Blender commit, lib commit, T0, gcc and cmake versions, checksums.
   - Split the archives under 2 GiB and upload them to a rolling release such as `blender-cache-main`.
   - Inside CI, keep the ccache warm between runs with the Actions cache (10 GB) so that later runs are
     fast.
3. **Add a `blender:restore <name>` mise task**, run on demand (by Claude when a task needs Blender C/C++,
   or from a SessionStart hook with `async: true`), not in the setup script. Together with ty, it won't fit
   the 5-minute snapshot window. Steps:
   1. Download and verify the parts.
   2. Create the worktree and the lib checkout at the manifest's commits, set every file's mtime to T0,
      extract the archives.
   3. `git checkout` the wanted commits (3.3).
   4. Run `blender:build`, which is then incremental.
   - GitHub Releases needs no secret, and the libraries come from `projects.blender.org`, which this
     environment already allows.
4. **Keep the final-outputs archive** (E) for the many sessions that never touch C/C++.

**Free / self-hosted alternative:**

- **For C/C++ work: Remote Control on your own machine.** It is natively incremental and needs no hosting
  and no cache.
- **For cloud sessions with write-back:** run nginx WebDAV or `bazel-remote` on your computer behind a
  Cloudflare named tunnel on your own domain. Add a network secret for that host (basic or bearer); that
  also allowlists it. Then point ccache 4.14 plus `ccache-storage-https` (the C++ helper, built once and
  shipped alongside ccache) at it. Sessions then read and write individual entries. This still means a
  replay build without approach A, so it complements A rather than replacing it.

**Top combinations:**

| # | Combination | Trade-off |
| --- | --- | --- |
| 1 | A + B on GitHub Releases, produced by GitHub Actions | free and allowlisted, meets the requirement; the most moving parts (exact path, toolchain and checkout order) |
| 2 | Remote Control on your machine | zero hosting, natively incremental; your computer must be on, and the session isn't a cloud VM |
| 3 | ccache with HTTPS remote storage on your machine (or a Hetzner Storage Box) through a network secret | write-back and sharing between sessions; a replay build every fresh session, and a helper to build and host to allowlist |

**Not recommended:**

- Hugging Face, Internet Archive and SourceForge (policy and proxy).
- Google Drive (quota lockouts, OAuth churn).
- distcc (proxy).
- sccache with remote storage (no preprocessor cache mode remotely, signing credentials).
- Docker Hub as the main host (shared anonymous pull limits).

## 8. Open questions (unverified)

1. **Real sizes and times:** Release `full` build dir, install dir and ccache size; a cold build on 4 vCPU
   with 2 and 4 jobs; a ccache replay build; an incremental rebuild after a one-file edit, including the
   `blender` relink. Measure in the first CI run (`ccache -s`, `du -sh`, `.ninja_log`).
2. **Does the A-restore really rebuild only the edited file?** Check with `ninja -d explain -n` after a
   restore and one `touch`, both in a container that copies the cloud image and in a real cloud session.
3. **uv's environment path for `scripts/build_blender.py`:** is the `cmake`/`ninja` path in
   `configure-args.txt` stable between CI and the cloud? If not, does the forced reconfigure leave
   compile commands unchanged?
4. **The environment snapshot:** does it keep `.cache/` inside the repo, or is the repo re-cloned per
   session? (Same as open question 2 of the earlier note.) That decides whether the restore can live in
   setup at all, and where it extracts to.
5. **API surface of presets:** does `headless` give the same `bpy` API (and stubs) as `full`, so that it
   could replace `full` in CI?
6. **ccache hit rate across CI and the cloud** with `base_dir`, `compiler_check='%compiler% -v'` and the
   two PCH targets. Do CMake's PCH flags with GCC meet ccache's PCH requirements, or do those targets
   always miss?
7. **The R2 S3 endpoint with a real account** through this proxy, and whether R2 presigned URLs work
   here.
8. **Drive's `alt=media` redirects:** does a download stay on `www.googleapis.com`, or redirect to a
   blocked host?
9. **Does the ccache C++ HTTPS helper actually work through the agent proxy** (libcurl, proxy CA,
   HTTP/2)? Does a network-secret header get added to its `PUT`s?
10. **Docker Hub anonymous pull limits** from the shared proxy egress IPs.
11. **Does `production.cloudflare.docker.com` serve large OCI blobs** without size limits that would
    matter for multi-GB layers?
