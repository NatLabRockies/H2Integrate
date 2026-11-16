import os

import psutil
import pytest


GIB = 1024**3
MEMORY_RESERVE = GIB
MEMORY_PER_WORKER = 2 * GIB


def memory_limited_workers(cpu_count: int, available_memory: int) -> int:
    """Limit automatic workers to the available CPUs and memory."""
    memory_workers = max(0, (available_memory - MEMORY_RESERVE) // MEMORY_PER_WORKER)
    workers = min(cpu_count, memory_workers)
    return workers if workers >= 2 else 0


@pytest.hookimpl(tryfirst=True, optionalhook=True)
def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    if os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS"):
        return None

    logical = config.option.numprocesses == "logical"
    cpu_count = psutil.cpu_count(logical=logical) or os.cpu_count() or 1
    process = psutil.Process()
    if hasattr(process, "cpu_affinity"):
        cpu_count = min(cpu_count, len(process.cpu_affinity()))
    return memory_limited_workers(cpu_count, psutil.virtual_memory().available)
