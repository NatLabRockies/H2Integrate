from pathlib import Path

import pytest
from pytest import fixture

from h2integrate import H2IntegrateModel, load_yaml, load_driver_yaml
from h2integrate.postprocess.sql_timeseries_to_csv import save_case_timeseries_as_csv


@fixture
def configuration(temp_copy_of_example):
    example_folder = temp_copy_of_example
    config = load_yaml(example_folder / "natgas.yaml")

    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")
    output_folder = example_folder / driver_config["general"]["folder_output"]
    driver_config["general"]["folder_output"] = str(output_folder)
    driver_config["recorder"] = {
        "flag": True,
        "file": "cases.sql",
        "overwrite_recorder": True,
        "recorder_attachment": "model",
        "includes": ["*"],
        "excludes": ["*resource_data*"],
    }
    config["driver_config"] = driver_config

    return config


@fixture
def run_example_sql_fpath(configuration):
    # check if case file exists, if so, return the filepath
    output_folder = (
        Path(configuration["driver_config"]["general"]["folder_output"]).resolve().parent
    )
    sql_fpath = output_folder / "cases.sql"
    if sql_fpath.exists():
        return sql_fpath
    else:
        # Create a H2Integrate model
        h2i = H2IntegrateModel(configuration)

        # Run the model
        h2i.run()

        return h2i.recorder_path.absolute()


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("16_natural_gas", "11_hybrid_energy_plant")]
)
def test_save_csv_all_results(subtests, configuration, run_example_sql_fpath):
    expected_csv_fpath = (
        Path(configuration["driver_config"]["general"]["folder_output"]) / "cases_Case-1.csv"
    )
    res = save_case_timeseries_as_csv(run_example_sql_fpath, save_to_file=True)

    with subtests.test("Check number of columns"):
        assert len(res.columns.to_list()) > 0

    with subtests.test("Check number of rows"):
        assert len(res) == 8760

    with subtests.test("CSV File exists"):
        assert expected_csv_fpath.exists()


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("16_natural_gas", "11_hybrid_energy_plant")]
)
def test_make_df_from_varname_list(subtests, run_example_sql_fpath):
    vars_to_save = [
        "natural_gas_plant.electricity_out",
        "elec_combiner.electricity_out",
        "solar.electricity_out",
        "battery.electricity_out",
    ]

    res = save_case_timeseries_as_csv(
        run_example_sql_fpath, vars_to_save=vars_to_save, save_to_file=False
    )

    with subtests.test("Check number of columns"):
        assert len(res.columns.to_list()) == len(vars_to_save)

    with subtests.test("Check number of rows"):
        assert len(res) == 8760

    with subtests.test("All vars in dataframe"):
        colnames_no_units = [c.split("(")[0].strip() for c in res.columns.to_list()]
        assert all(var_name in colnames_no_units for var_name in vars_to_save)


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("16_natural_gas", "11_hybrid_energy_plant")]
)
def test_make_df_from_varname_unit_dict(subtests, run_example_sql_fpath):
    vars_units_to_save = {
        "natural_gas_plant.natural_gas_in": "MMBtu/h",
        "battery.electricity_in": "kW",
        "solar.electricity_out": "kW",
    }

    res = save_case_timeseries_as_csv(
        run_example_sql_fpath, vars_to_save=vars_units_to_save, save_to_file=False
    )

    with subtests.test("Check number of columns"):
        assert len(res.columns.to_list()) == len(vars_units_to_save)

    with subtests.test("Check number of rows"):
        assert len(res) == 8760

    with subtests.test("All vars in dataframe"):
        expected_colnames = [
            f"{v_name} ({v_unit})" for v_name, v_unit in vars_units_to_save.items()
        ]
        assert all(c_name in res.columns.to_list() for c_name in expected_colnames)


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("16_natural_gas", "11_hybrid_energy_plant")]
)
def test_alternative_column_names(subtests, run_example_sql_fpath):
    vars_to_save = {
        "natural_gas_plant.electricity_out": {
            "alternative_name": "Natural Gas Plant Electricity Output"
        },
        "elec_combiner.electricity_out": {
            "units": "kW",
            "alternative_name": "Plant Electricity Output",
        },
        "solar.electricity_out": {"alternative_name": None},
        "battery.electricity_out": {"alternative_name": "Battery Electricity Output"},
    }

    res = save_case_timeseries_as_csv(
        run_example_sql_fpath,
        vars_to_save=vars_to_save,
        save_to_file=False,
    )

    expected_name_list = [
        "Natural Gas Plant Electricity Output (MW)",
        "Plant Electricity Output (kW)",
        "solar.electricity_out (MW)",
        "Battery Electricity Output (MW)",
    ]

    with subtests.test("Check number of columns"):
        assert len(res.columns.to_list()) == len(vars_to_save)

    with subtests.test("Check number of rows"):
        assert len(res) == 8760

    with subtests.test("All vars in dataframe with units"):
        expected_colnames = [f"{v_name}" for v_name in expected_name_list]
        assert all(c_name in res.columns.to_list() for c_name in expected_colnames)
