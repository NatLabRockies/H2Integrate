import os

import numpy as np
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.postprocess.sql_timeseries_to_csv import save_case_timeseries_as_csv


@fixture
def run_example_02_sql_fpath():
    # check if case file exists, if so, return the filepath
    sql_fpath = EXAMPLE_DIR / "02_texas_ammonia" / "outputs" / "cases.sql"
    if sql_fpath.exists():
        return sql_fpath
    else:
        os.chdir(EXAMPLE_DIR / "02_texas_ammonia")
        # Create a H2Integrate model
        h2i = H2IntegrateModel("02_texas_ammonia.yaml")

        # Set the demand profile
        demand_profile = np.ones(8760) * 640.0
        h2i.setup()
        h2i.prob.set_val("battery.electricity_demand", demand_profile, units="MW")

        # Run the model
        h2i.run()

        return h2i.recorder_path.absolute()


def test_save_csv_all_results(subtests, run_example_02_sql_fpath):
    expected_csv_fpath = EXAMPLE_DIR / "02_texas_ammonia" / "outputs" / "cases_Case-1.csv"
    res = save_case_timeseries_as_csv(run_example_02_sql_fpath, save_to_file=True)

    with subtests.test("Check number of columns"):
        assert len(res.columns.to_list()) == 35

    with subtests.test("Check number of rows"):
        assert len(res) == 8760

    with subtests.test("CSV File exists"):
        assert expected_csv_fpath.exists()


def test_make_df_from_varname_list(subtests, run_example_02_sql_fpath):
    vars_to_save = [
        "electrolyzer.hydrogen_out",
        "combiner.electricity_out",
        "ammonia.ammonia_out",
        "h2_storage.hydrogen_out",
    ]

    res = save_case_timeseries_as_csv(
        run_example_02_sql_fpath, vars_to_save=vars_to_save, save_to_file=False
    )

    with subtests.test("Check number of columns"):
        assert len(res.columns.to_list()) == len(vars_to_save)

    with subtests.test("Check number of rows"):
        assert len(res) == 8760

    with subtests.test("All vars in dataframe"):
        colnames_no_units = [c.split("(")[0].strip() for c in res.columns.to_list()]
        assert all(var_name in colnames_no_units for var_name in vars_to_save)


def test_make_df_from_varname_unit_dict(subtests, run_example_02_sql_fpath):
    vars_units_to_save = {
        "ammonia.hydrogen_in": "kg/h",
        "h2_storage.hydrogen_in": "kg/h",
        "electrolyzer.electricity_in": "kW",
    }

    res = save_case_timeseries_as_csv(
        run_example_02_sql_fpath, vars_to_save=vars_units_to_save, save_to_file=False
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


def test_alternative_column_names(subtests, run_example_02_sql_fpath):
    vars_to_save = {
        "electrolyzer.hydrogen_out": {"alternative_name": "Electrolyzer Hydrogen Output"},
        "combiner.electricity_out": {"units": "kW", "alternative_name": "Plant Electricity Output"},
        "ammonia.ammonia_out": {"alternative_name": None},
        "h2_storage.hydrogen_out": {"alternative_name": "H2 Storage Hydrogen Output"},
    }

    res = save_case_timeseries_as_csv(
        run_example_02_sql_fpath,
        vars_to_save=vars_to_save,
        save_to_file=False,
    )

    expected_name_list = [
        "Electrolyzer Hydrogen Output (kg/h)",
        "Plant Electricity Output (kW)",
        "ammonia.ammonia_out (kg/h)",
        "H2 Storage Hydrogen Output (kg/h)",
    ]

    with subtests.test("Check number of columns"):
        assert len(res.columns.to_list()) == len(vars_to_save)

    with subtests.test("Check number of rows"):
        assert len(res) == 8760

    with subtests.test("All vars in dataframe with units"):
        expected_colnames = [f"{v_name}" for v_name in expected_name_list]
        assert all(c_name in res.columns.to_list() for c_name in expected_colnames)
