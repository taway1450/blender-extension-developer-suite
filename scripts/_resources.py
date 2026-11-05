"""Keep the tasks from making the machine unusable.

Every task enters through ``_common.main_wrapper``, which runs it inside :func:`guarded`:

- **One heavy task at a time, machine-wide.** A file lock in the temp directory is shared by every checkout and
  worktree of this repo, so tasks started by parallel agents queue instead of building ty or running Blender side
  by side. The operating system frees the lock when the process exits, even after a crash. Tasks a guarded task
  starts inherit the lock through ``SUITE_LOCK_HELD``.
- **Fewer threads.** ``CARGO_BUILD_JOBS``, ``TY_MAX_PARALLELISM``, ``NEXTEST_TEST_THREADS`` and
  ``CMAKE_BUILD_PARALLEL_LEVEL`` default to half the logical CPUs. ``SUITE_JOBS`` overrides them all, and a variable
  that is already set is kept.
- **A memory ceiling (Windows).** The task and every process it starts run in a job object whose committed
  memory is capped at half the physical memory (``SUITE_MEMORY_LIMIT_GB`` overrides it, ``0`` turns it off). A
  build that reaches the cap fails with an allocation error instead of swapping the machine to a halt.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK_PATH = Path(tempfile.gettempdir()) / "blender-extension-developer-suite.lock"
LOCK_HELD = "SUITE_LOCK_HELD"
THREAD_VARIABLES = ("CARGO_BUILD_JOBS", "TY_MAX_PARALLELISM", "NEXTEST_TEST_THREADS", "CMAKE_BUILD_PARALLEL_LEVEL")


def default_jobs() -> int:
    if jobs := os.environ.get("SUITE_JOBS"):
        return max(1, int(jobs))
    return max(1, (os.cpu_count() or 2) // 2)


def limit_threads(environ: dict[str, str] | os._Environ[str] = os.environ) -> int:
    """Set the thread variables that are not set yet; the number of jobs."""
    jobs = default_jobs()
    for name in THREAD_VARIABLES:
        environ.setdefault(name, str(jobs))
    return jobs


def memory_limit_bytes() -> int | None:
    """The memory ceiling for the task and its processes, or ``None`` for none."""
    if (setting := os.environ.get("SUITE_MEMORY_LIMIT_GB")) is not None:
        gigabytes = float(setting)
        return int(gigabytes * 1024**3) if gigabytes > 0 else None
    physical = physical_memory_bytes()
    return physical // 2 if physical else None


def physical_memory_bytes() -> int | None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        status = MemoryStatus(dwLength=ctypes.sizeof(MemoryStatus))
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys
        return None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def cap_memory(limit: int) -> bool:
    """Put this process, and so every process it starts, in a job object capped at ``limit`` bytes of committed
    memory. Windows only; ``False`` where that is not possible."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("r", "w", "o", "rb", "wb", "ob")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job_object_extended_limit_information = 9
    job_object_limit_job_memory = 0x200
    job_object_limit_kill_on_job_close = 0x2000

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return False
    limits = ExtendedLimits()
    # Kill on close: when the task exits or is killed, nothing it started survives it.
    limits.BasicLimitInformation.LimitFlags = job_object_limit_job_memory | job_object_limit_kill_on_job_close
    limits.JobMemoryLimit = limit
    if not kernel32.SetInformationJobObject(
        wintypes.HANDLE(job), job_object_extended_limit_information, ctypes.byref(limits), ctypes.sizeof(limits)
    ):
        return False
    # The handle stays open for the life of the process, which keeps the job (and its limit) alive.
    return bool(kernel32.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(kernel32.GetCurrentProcess())))


@contextmanager
def machine_lock(path: Path = LOCK_PATH, *, poll_seconds: float = 2.0) -> Iterator[None]:
    """Hold the machine-wide task lock; wait for it, saying so once, while another task holds it."""
    if os.environ.get(LOCK_HELD):
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")  # noqa: SIM115 (held until the context exits)
    try:
        waited = False
        while not try_lock(handle):
            if not waited:
                print(f"==> Waiting for another task to finish (lock {path})", flush=True)
                waited = True
            time.sleep(poll_seconds)
        os.environ[LOCK_HELD] = str(os.getpid())
        try:
            yield
        finally:
            os.environ.pop(LOCK_HELD, None)
            unlock(handle)
    finally:
        handle.close()


def try_lock(handle) -> bool:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def unlock(handle) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def guarded() -> Iterator[None]:
    """Run a task under the machine lock, with fewer threads and, on Windows, a memory ceiling."""
    nested = bool(os.environ.get(LOCK_HELD))
    with machine_lock():
        if not nested:
            jobs = limit_threads()
            limit = memory_limit_bytes()
            capped = limit is not None and cap_memory(limit)
            memory = f", memory capped at {limit / 1024**3:.1f} GB" if capped else ""
            print(f"==> Resource limits: {jobs} jobs{memory} (see scripts/_resources.py)", flush=True)
        yield
