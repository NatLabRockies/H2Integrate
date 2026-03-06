"""Unit tests for h2integrate.postprocess.sql_to_csv module.

These tests follow the same pattern as test_sql_timeseries_to_csv.py:
run example 19 (simple dispatch) to produce a real SQL recorder file,
then exercise convert_sql_to_csv_summary and summarize_case against it.
"""

import os
from pathlib import Path

import pandas as pd
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_yaml, load_tech_yaml, load_driver_yaml
from h2integrate.postprocess.sql_to_csv import summarize_case, convert_sql_to_csv_summary


# ---------------------------------------------------------------------------
# Fixtures — mirror the pattern from test_sql_timeseries_to_csv.py but
#             targeting example 19_simple_dispatch.
# ---------------------------------------------------------------------------

EXAMPLE_19_DIR = EXAMPLE_DIR / "19_simple_dispatch"


@fixture
def configuration(temp_dir):
    """Load and patch the example-19 configuration so outputs go to a temp dir."""
    config = load_yaml(EXAMPLE_19_DIR / "wind_battery_dispatch.yaml")

    driver_config = load_driver_yaml(EXAMPLE_19_DIR / "driver_config.yaml")
    driver_config["general"]["folder_output"] = str(temp_dir)
    # Add a recorder so that an SQL file is produced
    driver_config["recorder"] = {
        "flag": True,
        "file": "cases.sql",
        "overwrite_recorder": True,
        "recorder_attachment": "model",
        "includes": ["*"],
        "excludes": ["*resource_data*"],
    }
    config["driver_config"] = driver_config

    tech_config = load_tech_yaml(EXAMPLE_19_DIR / "tech_config.yaml")
    config["technology_config"] = tech_config
    return config


@fixture
def run_example_19_sql_fpath(configuration):
    """Run example 19 (or reuse cached SQL) and return the path to the SQL file."""
    output_dir = Path(configuration["driver_config"]["general"]["folder_output"])
    sql_fpath = output_dir / "cases.sql"
    if sql_fpath.exists():
        return sql_fpath

    os.chdir(EXAMPLE_19_DIR)
    h2i = H2IntegrateModel(configuration)
    h2i.run()

    return h2i.recorder_path.absolute()


# ---------------------------------------------------------------------------
# Tests for summarize_case
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_summarize_case_returns_dict(run_example_19_sql_fpath):
    """summarize_case should return a dictionary of scalar results."""
    cr = om.CaseReader(str(run_example_19_sql_fpath))
    case = list(cr.get_cases())[0]

    result = summarize_case(case)

    assert isinstance(result, dict)
    assert len(result) > 0


@pytest.mark.unit
def test_summarize_case_return_units(run_example_19_sql_fpath):
    """When return_units=True, summarize_case should return (values, units)."""
    cr = om.CaseReader(str(run_example_19_sql_fpath))
    case = list(cr.get_cases())[0]

    values, units = summarize_case(case, return_units=True)

    assert isinstance(values, dict)
    assert isinstance(units, dict)
    assert len(values) > 0
    assert len(units) > 0

    # Every key in units should also be in values
    for key in units:
        assert key in values, f"Unit key '{key}' missing from values dict"


@pytest.mark.unit
def test_summarize_case_scalar_only(run_example_19_sql_fpath):
    """summarize_case should only contain scalar (single-element) values, not timeseries."""
    cr = om.CaseReader(str(run_example_19_sql_fpath))
    case = list(cr.get_cases())[0]

    result = summarize_case(case)

    for var, val in result.items():
        # discrete values (str, bool, int, float) are fine
        if isinstance(val, str | bool):
            continue
        # numeric scalars should not be arrays with multiple elements
        assert (
            not hasattr(val, "__len__") or len([val]) == 1
        ), f"Variable '{var}' is not scalar: {val}"


@pytest.mark.unit
def test_summarize_case_known_variables(run_example_19_sql_fpath):
    """Expected variables from example 19 should appear in the summary."""
    cr = om.CaseReader(str(run_example_19_sql_fpath))
    case = list(cr.get_cases())[0]

    result = summarize_case(case)

    # Example 19 has wind + battery, so we expect CapEx for both
    expected_vars = ["wind.CapEx", "battery.CapEx"]
    for var in expected_vars:
        assert var in result, f"Expected '{var}' in summary, got keys: {list(result.keys())}"


# ---------------------------------------------------------------------------
# Tests for convert_sql_to_csv_summary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_file_not_found(tmp_path):
    """Should raise FileNotFoundError when the SQL file does not exist."""
    fake_path = tmp_path / "nonexistent.sql"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        convert_sql_to_csv_summary(fake_path)


@pytest.mark.unit
def test_returns_dataframe(run_example_19_sql_fpath):
    """convert_sql_to_csv_summary should return a pandas DataFrame."""
    result = convert_sql_to_csv_summary(run_example_19_sql_fpath, save_to_file=False)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1  # single run → one row


@pytest.mark.unit
def test_column_names_include_units(run_example_19_sql_fpath):
    """Columns for continuous variables should include units in parentheses."""
    result = convert_sql_to_csv_summary(run_example_19_sql_fpath, save_to_file=False)

    cols = result.columns.to_list()
    cols_with_units = [c for c in cols if "(" in c and ")" in c]
    assert len(cols_with_units) > 0, f"Expected columns with units, got: {cols}"


@pytest.mark.unit
def test_save_to_file_creates_csv(subtests, run_example_19_sql_fpath):
    """When save_to_file=True, a CSV file should be written next to the SQL file."""
    result = convert_sql_to_csv_summary(run_example_19_sql_fpath, save_to_file=True)

    expected_csv = run_example_19_sql_fpath.parent / f"{run_example_19_sql_fpath.stem}.csv"

    with subtests.test("CSV file exists"):
        assert expected_csv.exists(), "CSV file should have been created"

    with subtests.test("CSV is readable and matches DataFrame"):
        df = pd.read_csv(expected_csv, index_col=0)
        assert len(df) == len(result)
        assert list(df.columns) == list(result.columns)


@pytest.mark.unit
def test_save_to_file_false_no_csv(run_example_19_sql_fpath):
    """When save_to_file=False, no CSV file should be written."""
    csv_path = run_example_19_sql_fpath.parent / f"{run_example_19_sql_fpath.stem}.csv"
    # Remove any pre-existing CSV from earlier tests
    if csv_path.exists():
        csv_path.unlink()

    convert_sql_to_csv_summary(run_example_19_sql_fpath, save_to_file=False)

    assert not csv_path.exists(), "No CSV file should be created when save_to_file=False"


@pytest.mark.unit
def test_accepts_string_path(run_example_19_sql_fpath):
    """The function should accept a plain string path."""
    result = convert_sql_to_csv_summary(str(run_example_19_sql_fpath), save_to_file=False)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1


@pytest.mark.unit
def test_result_contains_expected_columns(run_example_19_sql_fpath):
    """The summary should contain known scalar outputs from example 19."""
    result = convert_sql_to_csv_summary(run_example_19_sql_fpath, save_to_file=False)

    cols = result.columns.to_list()
    # Strip units from column names for easier matching
    col_names_no_units = [c.split(" (")[0] for c in cols]

    expected_vars = ["wind.CapEx", "battery.CapEx"]
    for var in expected_vars:
        assert (
            var in col_names_no_units
        ), f"Expected '{var}' in summary columns, got: {col_names_no_units}"


@pytest.mark.unit
def test_result_has_single_row(run_example_19_sql_fpath):
    """A single run should produce exactly one row in the summary."""
    result = convert_sql_to_csv_summary(run_example_19_sql_fpath, save_to_file=False)

    assert len(result) == 1
    assert result.index.to_list() == [0]
