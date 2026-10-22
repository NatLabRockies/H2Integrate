"""Run every example script the same way a user would from the command line.

The value checks for each example live in ``test_all_examples.py``. These tests only confirm that
each ``run_*.py`` script, including its plotting and post-processing code, finishes without error.
"""

import os
import sys
import shutil
import subprocess
import importlib.util

import pytest

from h2integrate import EXAMPLE_DIR


# Python modules under examples/ that are imported by a run script or referenced from a config
HELPER_MODULES = {
    "03_methanol/co2_hydrogenation_doc/plot_co2h_methanol.py",
    "06_custom_tech/user_defined_model/paper_mill.py",
    "08_wind_electrolyzer/user_finance_model/simple_lco.py",
}

# Scripts that need an optional dependency, mapped to the module that must be importable
OPTIONAL_DEPENDENCIES = {
    "21_iron_examples/iron_mapping/run_iron.py": "geopandas",
    "29_wind_ard/run_windard_pv_battery.py": "ard",
}

SCRIPT_TIMEOUT_SECONDS = 3600


def _relative(path):
    return path.relative_to(EXAMPLE_DIR).as_posix()


def _example_python_files(pattern):
    return {
        _relative(path)
        for path in EXAMPLE_DIR.rglob(pattern)
        if path.relative_to(EXAMPLE_DIR).parts[0] != "test" and "__pycache__" not in path.parts
    }


EXAMPLE_SCRIPTS = sorted(_example_python_files("run_*.py"))


def _script_param(script):
    module = OPTIONAL_DEPENDENCIES.get(script)
    marks = []
    if module is not None:
        marks.append(
            pytest.mark.skipif(
                importlib.util.find_spec(module) is None, reason=f"{module} is not installed"
            )
        )
    return pytest.param(script, marks=marks, id=script)


@pytest.mark.unit
def test_example_scripts_are_discoverable():
    """Every example Python file is either a ``run_*.py`` script or a known helper module."""
    python_files = _example_python_files("*.py")
    unexpected = sorted(python_files - set(EXAMPLE_SCRIPTS) - HELPER_MODULES)
    assert not unexpected, (
        "Name example scripts `run_*.py` so they are tested, or add helper modules to "
        f"HELPER_MODULES in {__file__}: {unexpected}"
    )
    missing_helpers = sorted(HELPER_MODULES - python_files)
    assert not missing_helpers, f"Remove deleted files from HELPER_MODULES: {missing_helpers}"


@pytest.mark.examples
@pytest.mark.parametrize("script", [_script_param(script) for script in EXAMPLE_SCRIPTS])
def test_example_script_runs(script, tmp_path):
    """Run the script from a temporary copy of its top-level example folder."""
    example_root = script.split("/")[0]
    shutil.copytree(
        EXAMPLE_DIR / example_root,
        tmp_path / example_root,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    script_path = tmp_path / script

    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    env["OPENMDAO_REPORTS"] = "none"
    env["PYTHONIOENCODING"] = "utf-8"
    # Import the h2integrate source tree under test, even when the package is installed elsewhere
    python_path = [str(EXAMPLE_DIR.parent), env.get("PYTHONPATH", "")]
    env["PYTHONPATH"] = os.pathsep.join(path for path in python_path if path)

    result = subprocess.run(
        [sys.executable, script_path.name],
        cwd=script_path.parent,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SCRIPT_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, (
        f"{script} exited with code {result.returncode}\n"
        f"--- stdout (last 3000 characters) ---\n{result.stdout[-3000:]}\n"
        f"--- stderr (last 6000 characters) ---\n{result.stderr[-6000:]}"
    )
