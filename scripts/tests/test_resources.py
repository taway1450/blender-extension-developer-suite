import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import _resources


def test_limit_threads_keeps_variables_that_are_set(monkeypatch):
    monkeypatch.setenv("SUITE_JOBS", "3")
    environ = {"CARGO_BUILD_JOBS": "12"}
    assert _resources.limit_threads(environ) == 3
    assert environ["CARGO_BUILD_JOBS"] == "12"
    assert environ["TY_MAX_PARALLELISM"] == "3"
    assert environ["NEXTEST_TEST_THREADS"] == "3"


def test_default_jobs_is_half_the_cpus(monkeypatch):
    monkeypatch.delenv("SUITE_JOBS", raising=False)
    monkeypatch.setattr(_resources.os, "cpu_count", lambda: 16)
    assert _resources.default_jobs() == 8


@pytest.mark.parametrize(("setting", "expected"), [("0", None), ("2", 2 * 1024**3)])
def test_memory_limit_setting(monkeypatch, setting, expected):
    monkeypatch.setenv("SUITE_MEMORY_LIMIT_GB", setting)
    assert _resources.memory_limit_bytes() == expected


def test_memory_limit_defaults_to_half_the_physical_memory(monkeypatch):
    monkeypatch.delenv("SUITE_MEMORY_LIMIT_GB", raising=False)
    monkeypatch.setattr(_resources, "physical_memory_bytes", lambda: 32 * 1024**3)
    assert _resources.memory_limit_bytes() == 16 * 1024**3


def try_lock_in_other_process(lock: Path) -> str:
    """Whether another process can take the lock right now."""
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(Path(_resources.__file__).parent)!r})
        import _resources
        with open({str(lock)!r}, "a+b") as handle:
            print("free" if _resources.try_lock(handle) else "held")
        """
    )
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()


def test_machine_lock_excludes_other_processes(tmp_path, monkeypatch):
    monkeypatch.delenv(_resources.LOCK_HELD, raising=False)
    lock = tmp_path / "suite.lock"
    with _resources.machine_lock(lock):
        assert try_lock_in_other_process(lock) == "held"
        # A task started by the task holding the lock (it inherits the variable) does not wait.
        with _resources.machine_lock(lock):
            pass
    assert try_lock_in_other_process(lock) == "free"
