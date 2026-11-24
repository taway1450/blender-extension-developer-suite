# Hosting the Blender fork on GitHub instead of projects.blender.org

Research note, 2026-11-24. Question: should the `blender` submodule (`projects.blender.org/Simon-Sak/blender`)
move to a fork of the GitHub mirror `github.com/blender/blender`? Prompted by run 4 of the Blender cache
workflow, whose anonymous clone of the submodule got HTTP 403 from projects.blender.org twice (run 5, started a
few hours later with the same clone plus retries, cloned fine). Facts marked *measured* were checked in a
cloud session; the GitHub documentation pages were not reachable from it, so the LFS rules come from search
results of those pages and are marked *docs, via search*.

## What the submodule pulls from projects.blender.org

| What | From | Size | Needed by the build |
| --- | --- | --- | --- |
| Git history (`--filter=blob:none`) | `Simon-Sak/blender` | 198 MB, 35 s | yes |
| Blobs of one checkout | same, on demand | ~1.2 GB with LFS | yes |
| LFS files of the source | `Simon-Sak/blender.git/info/lfs` | 898 MB, of which `tests/files` 871 MB | only `release/`, `assets/` (~27 MB) |
| Precompiled libraries | `blender/lib-linux_x64` (a submodule of the source, with LFS) | 4.4 GB checkout, 2.1 GB `.git` | yes (headers and `.a` files, also for every incremental link) |

*Measured.* `tests/files` is used only by Blender's own tests: the `full` preset has `WITH_GTESTS=OFF`, and
the suite's checks read `tests/python/*.py`, which are not LFS files.

## The fork

*Measured* against `projects.blender.org/blender/blender` `main` (932a88ccf6, 2026-11-24):

| Branch | Ahead of upstream | Behind |
| --- | --- | --- |
| `main` | 0 | 515 |
| `typecheck-fixes` (what the submodule pins) | 235 | 255 |
| `stub-generator` | 87 | 255 |
| `source-facts-makesrna` | 2 | 5142 |

None of the fork's own commits touch an LFS-tracked path, so every LFS object the fork needs is also
upstream's. The GitHub mirror is current (its `main` is 932a88ccf6 too) and has `faa17d9072`, the commit the
cache builds. A `--filter=blob:none` clone of the GitHub mirror took 23 s (218 MB), against 35 s (198 MB)
from projects.blender.org: no real difference.

## What moving the fork to GitHub would and would not change

1. **projects.blender.org stays in the path either way.** The precompiled libraries (`lib-linux_x64`, 4.4 GB,
   LFS) exist only there; the source's `.gitmodules` names them by absolute URL. Mirroring them to GitHub
   LFS is not practical: 4.4 GB per download against GitHub Free's 10 GiB of LFS bandwidth a month
   (*docs, via search*; older pages say 1 GiB) is about two downloads.
2. **LFS of the source.** The GitHub mirror is pushed by Blender; whether it carries the LFS objects is
   unverified (the session's git proxy serves anonymous GitHub reads but not LFS, so it could not be
   checked here). A fork made with GitHub's fork button is in `blender/blender`'s fork network: its LFS
   storage and bandwidth count against the network's root, and LFS pushes to a public fork are accepted
   only if the network already has LFS objects or the pusher can write to the root (*docs, via search*;
   one community report describes LFS pushes to a fork refused because the root had no LFS budget). So a
   GitHub *fork* cannot be relied on for LFS. A plain repository (`taway1450/blender`, pushed from the
   projects.blender.org fork, not a fork on GitHub) could hold the ~27 MB the build needs in its own
   quota, or point `lfs.url` back at `projects.blender.org/blender/blender.git/info/lfs`.
3. **Cloud sessions.** projects.blender.org works there: the proxy injects credentials for it. A GitHub
   repository would have to be added to the session's sources for its LFS objects (the anonymous lane does
   not serve LFS); a public one clones without that.
4. **Contributing back.** Pull requests to Blender are made from a fork on projects.blender.org, so that
   fork stays and a GitHub copy is a second remote to push every branch to.
5. **CI.** A GitHub repository would avoid projects.blender.org's occasional 403 for the clone, but not
   for the libraries and LFS files the build step fetches next from the same host.

## Recommendation

Not worth it now. It adds a mirror to keep in sync and leaves the large downloads (libraries, LFS) on
projects.blender.org, which is where the risk is. Do these instead:

1. **Skip `tests/files` in `build_blender.py`'s LFS pull** (`git lfs pull --exclude=tests/files`, or
   `lfs.fetchexclude` on the worktree): 871 of the 898 MB, on every fresh worktree, in CI and in sessions.
2. **Retry projects.blender.org fetches with backoff** in CI (done for the submodule clone; the library
   and LFS fetches inside `blender:build` could get the same).
3. **If projects.blender.org keeps refusing runners**, ship the libraries with the build cache: a release
   asset of `lib/linux_x64`'s checkout (no `.git`) next to the build directory, which `blender:restore`
   unpacks. A session restoring the cache would then need projects.blender.org only for the source.
4. Revisit a GitHub copy only if the *source* clone itself becomes the bottleneck; make it a plain
   repository, not a GitHub fork, because of the LFS rules in point 2.

Sources (via search; docs.github.com was not reachable from the session):
[about storage and bandwidth usage](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-storage-and-bandwidth-usage),
[collaboration with Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/collaboration-with-git-large-file-storage),
[Git LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs),
[community discussion #151710](https://github.com/orgs/community/discussions/151710).
