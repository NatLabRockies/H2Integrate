import os
from pathlib import Path

import pytest

from h2integrate import EXAMPLE_DIR
from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases
from h2integrate.core.h2integrate_model import H2IntegrateModel


def test_tech_config_modifier(subtests):
    """Test cases for modifying and running tech_config from csv.
    Using 15 example as test case
    """

    # Make an H2I model from the 15 example
    os.chdir(EXAMPLE_DIR / "15_wind_solar_electrolyzer")
    example_yaml = "15_wind_solar_electrolyzer.yaml"
    model = H2IntegrateModel(example_yaml)

    # Modify using csv
    case_file = Path(__file__).resolve().parent / "test_inputs.csv"
    cases = load_tech_config_cases(case_file)
    with subtests.test("float"):
        case = cases["Float Test"]
        model = modify_tech_config(model, case)
        model.run()
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0], rel=1e-3
            )
            == 5.306335842372589
        )
    with subtests.test("bool"):
        case = cases["Bool Test"]
        model = modify_tech_config(model, case)
        model.run()
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0], rel=1e-3
            )
            == 5.205991056910428
        )
    with subtests.test("int"):
        case = cases["Int Test"]
        model = modify_tech_config(model, case)
        model.run()
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0], rel=1e-3
            )
            == 5.438566222420234
        )
    with subtests.test("str"):
        case = cases["Str Test"]
        model = modify_tech_config(model, case)
        model.run()
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0], rel=1e-3
            )
            == 5.205991056616438
        )
    with subtests.test("int repeat without run setup modify_tech_config"):
        case = cases["Int Test"]
        model = modify_tech_config(model, case, run_setup=False)
        model.run()
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0], rel=1e-3
            )
            == 5.205991056616438  # should still "str" test value
        )
    with subtests.test("int repeat with run setup outside modify_tech_config"):
        case = cases["Int Test"]
        model = modify_tech_config(model, case, run_setup=False)
        model.setup()
        model.run()
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0], rel=1e-3
            )
            == 5.438566222420234  # should still "str" test value
        )
