from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test.xdist_policy import memory_limited_workers, pytest_xdist_auto_num_workers


@pytest.mark.unit
@pytest.mark.parametrize(
    "cpu_count,available_gib,expected",
    [
        (16, 1, 0),
        (16, 3, 0),
        (16, 4, 0),
        (16, 5, 2),
        (16, 7, 3),
        (16, 9, 4),
        (4, 20, 4),
        (1, 20, 0),
    ],
    ids=[
        "low-memory",
        "reserve",
        "one-worker",
        "two-workers",
        "three-workers",
        "four-workers",
        "cpu-limit",
        "single-cpu",
    ],
)
def test_memory_limited_workers(cpu_count, available_gib, expected):
    assert memory_limited_workers(cpu_count, available_gib * 1024**3) == expected


@pytest.mark.unit
def test_memory_limited_workers_at_parallel_threshold():
    assert memory_limited_workers(8, 5 * 1024**3 - 1) == 0
    assert memory_limited_workers(8, 5 * 1024**3) == 2
    assert memory_limited_workers(8, 9 * 1024**3 - 1) == 3
    assert memory_limited_workers(8, 9 * 1024**3) == 4


@pytest.mark.unit
def test_xdist_auto_worker_policy(monkeypatch, subtests):
    config = SimpleNamespace(option=SimpleNamespace(numprocesses="auto"))
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    cpu_count = Mock(return_value=8)
    monkeypatch.setattr("test.xdist_policy.psutil.cpu_count", cpu_count)
    monkeypatch.setattr(
        "test.xdist_policy.psutil.virtual_memory", lambda: SimpleNamespace(available=9 * 1024**3)
    )
    monkeypatch.setattr(
        "test.xdist_policy.psutil.Process",
        lambda: SimpleNamespace(cpu_affinity=lambda: [0, 1, 2]),
    )

    with subtests.test("auto respects CPU affinity and memory"):
        assert pytest_xdist_auto_num_workers(config) == 3
        cpu_count.assert_called_with(logical=False)

    with subtests.test("logical mode requests logical CPUs"):
        config.option.numprocesses = "logical"
        assert pytest_xdist_auto_num_workers(config) == 3
        cpu_count.assert_called_with(logical=True)

    with subtests.test("platforms without affinity use the CPU count"):
        monkeypatch.setattr("test.xdist_policy.psutil.Process", lambda: SimpleNamespace())
        assert pytest_xdist_auto_num_workers(config) == 4

    with subtests.test("xdist handles the explicit environment override"):
        monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "5")
        assert pytest_xdist_auto_num_workers(config) is None
