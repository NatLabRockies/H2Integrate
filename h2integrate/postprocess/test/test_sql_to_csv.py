"""Tests for scalar summaries of a real OpenMDAO recorder file."""

import numpy as np
import pandas as pd
import pytest
import openmdao.api as om

from h2integrate import H2IntegrateModel, load_yaml, load_tech_yaml, load_driver_yaml
from h2integrate.postprocess.sql_to_csv import summarize_case, convert_sql_to_csv_summary


@pytest.fixture
def recorded_case(temp_copy_of_example_module_scope):
    example_folder = temp_copy_of_example_module_scope
    sql_path = example_folder / "cases.sql"
    if not sql_path.exists():
        config = load_yaml(example_folder / "wind_battery_dispatch.yaml")
        driver_config = load_driver_yaml(example_folder / "driver_config.yaml")
        driver_config["general"]["folder_output"] = str(example_folder)
        driver_config["recorder"] = {
            "flag": True,
            "file": "cases.sql",
            "overwrite_recorder": True,
            "recorder_attachment": "model",
            "includes": ["*"],
            "excludes": ["*resource_data*"],
        }
        config["driver_config"] = driver_config
        config["technology_config"] = load_tech_yaml(example_folder / "tech_config.yaml")
        model = H2IntegrateModel(config)
        model.run()
        sql_path = model.recorder_path.absolute()
    return sql_path


@pytest.mark.unit
@pytest.mark.parametrize("example_folder,resource_example_folder", [("19_simple_dispatch", None)])
def test_summarize_case(recorded_case, subtests):
    case = list(om.CaseReader(str(recorded_case)).get_cases())[0]
    values, units = summarize_case(case, return_units=True)

    with subtests.test("summary and units"):
        assert values == summarize_case(case)
        assert values
        assert units
        assert units.keys() <= values.keys()
        assert {"wind.CapEx", "battery.CapEx"} <= values.keys()
    with subtests.test("timeseries are excluded"):
        assert "wind.electricity_out" not in values
        assert all(np.isscalar(value) for value in values.values())


@pytest.mark.unit
def test_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        convert_sql_to_csv_summary(tmp_path / "nonexistent.sql")


@pytest.mark.unit
@pytest.mark.parametrize("example_folder,resource_example_folder", [("19_simple_dispatch", None)])
def test_convert_summary(recorded_case, subtests):
    csv_path = recorded_case.with_suffix(".csv")
    result = convert_sql_to_csv_summary(str(recorded_case), save_to_file=False)

    with subtests.test("single case with named scalar columns and units"):
        assert isinstance(result, pd.DataFrame)
        assert result.index.to_list() == [0]
        assert {"wind.CapEx", "battery.CapEx"} <= {name.split(" (")[0] for name in result.columns}
        assert any(" (" in name and name.endswith(")") for name in result.columns)
        assert not csv_path.exists()

    saved = convert_sql_to_csv_summary(recorded_case, save_to_file=True)
    with subtests.test("CSV matches the returned values"):
        pd.testing.assert_frame_equal(saved, result)
        assert csv_path.exists()
        pd.testing.assert_frame_equal(pd.read_csv(csv_path, index_col=0), result, check_dtype=False)
