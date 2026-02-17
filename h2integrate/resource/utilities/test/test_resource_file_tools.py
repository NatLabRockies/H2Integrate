import os
from pathlib import Path

import pytest

from h2integrate import EXAMPLE_DIR, RESOURCE_DEFAULT_DIR
from h2integrate.resource.utilities.file_tools import check_resource_dir


@pytest.mark.unit
def test_check_resource_dir_no_dir(subtests):
    output_dir = check_resource_dir()
    with subtests.test("No resource_dir, no resource_subdir"):
        assert output_dir == RESOURCE_DEFAULT_DIR

    output_dir = check_resource_dir(resource_subdir="wind")
    with subtests.test("No resource_dir, with resource_subdir"):
        expected_output_dir = RESOURCE_DEFAULT_DIR / "wind"
        assert output_dir == expected_output_dir


@pytest.mark.unit
def test_check_resource_dir_relative_dir_exists(subtests):
    os.chdir(EXAMPLE_DIR / "11_hybrid_energy_plant")
    relative_dir = "tech_inputs/weather"
    expected_dir = EXAMPLE_DIR / "11_hybrid_energy_plant" / "tech_inputs" / "weather"
    output_dir = check_resource_dir(resource_dir=relative_dir)
    with subtests.test("Relative resource_dir, no resource_subdir"):
        assert output_dir == expected_dir

    relative_dir = "tech_inputs/weather"
    expected_dir = EXAMPLE_DIR / "11_hybrid_energy_plant" / "tech_inputs" / "weather" / "wind"
    output_dir = check_resource_dir(resource_dir=relative_dir, resource_subdir="wind")
    with subtests.test("Relative resource_dir, with resource_subdir"):
        assert output_dir == expected_dir


@pytest.mark.unit
def test_check_resource_dir_full_dir_exists(subtests):
    expected_dir = EXAMPLE_DIR / "11_hybrid_energy_plant" / "tech_inputs" / "weather"
    output_dir = check_resource_dir(resource_dir=expected_dir)
    with subtests.test("Full resource_dir, no resource_subdir"):
        assert output_dir == expected_dir

    output_dir = check_resource_dir(resource_dir=expected_dir, resource_subdir="wind")
    with subtests.test("Full resource_dir, with resource_subdir"):
        assert str(output_dir) == str(expected_dir / "wind")


@pytest.mark.unit
def test_check_resource_dir_environment_var(subtests):
    resource_dir = str(EXAMPLE_DIR / "11_hybrid_energy_plant" / "tech_inputs" / "weather")
    os.environ["RESOURCE_DIR"] = resource_dir
    output_dir = check_resource_dir()
    with subtests.test("Environment variable resource_dir, no resource_subdir"):
        assert str(output_dir) == resource_dir

    output_dir = check_resource_dir(resource_subdir="wind")
    with subtests.test("Environment variable resource_dir, with resource_subdir"):
        assert str(output_dir) == str(Path(resource_dir) / "wind")

    # unset environment variable for other tests
    os.environ.pop("RESOURCE_DIR", None)
    assert os.getenv("RESOURCE_DIR") is None
