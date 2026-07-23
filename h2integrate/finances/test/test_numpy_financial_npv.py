import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.finances.numpy_financial_npv import (
    NumpyFinancialNPV,
    NumpyFinancialNPVFinanceConfig,
)


@fixture
def npv_finance_inputs():
    npv_dict = {
        "discount_rate": 0.09,
        "commodity_sell_price": 0.04,
        "commodity_sell_price_units": "USD/(kW*h)",
        "save_cost_breakdown": False,
        "save_npv_breakdown": False,
        "cost_breakdown_file_description": False,
    }
    return npv_dict


@fixture
def fake_filtered_tech_config():
    tech_config = {
        "wind": {"model_inputs": {}},
        "solar": {"model_inputs": {}},
        "battery": {"model_inputs": {}},
        "natural_gas": {"model_inputs": {}},
    }
    return tech_config


@fixture
def fake_cost_dict():
    fake_costs = {
        "capex_adjusted_wind": 950054634.1,
        "opex_adjusted_wind": 21093892.68,
        "varopex_adjusted_wind": [0.0] * 30,
        "capex_adjusted_solar": 6561339.6,
        "opex_adjusted_solar": 88372.77,
        "varopex_adjusted_solar": [0.0] * 30,
        "capex_adjusted_battery": 3402926,
        "opex_adjusted_battery": 779.27,
        "varopex_adjusted_battery": [0.0] * 30,
        "capex_adjusted_natural_gas": 1170731708.0,
        "opex_adjusted_natural_gas": 12783853.58,
        "varopex_adjusted_natural_gas": [65458026.9] * 30,
    }
    return fake_costs


@pytest.mark.regression
def test_simple_npv(npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests):
    mean_hourly_production = 500000.0
    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": npv_finance_inputs},
    }
    pf = NumpyFinancialNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )

    ivc = om.IndepVarComp()
    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [1.0] * 30, units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("npv", pf, promotes=["*"])
    prob.setup()

    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"npv.{variable}", cost, units=units)

    prob.run_model()

    with subtests.test("Sell price"):
        assert (
            pytest.approx(
                prob.get_val("npv.sell_price_electricity_no1", units="USD/(kW*h)"), rel=1e-6
            )
            == npv_finance_inputs["commodity_sell_price"]
        )

    with subtests.test("NPV"):
        assert (
            pytest.approx(prob.get_val("npv.NPV_electricity_no1", units="USD")[0], rel=1e-6)
            == -1352263704.120
        )


@pytest.mark.regression
def test_simple_npv_positive(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    mean_hourly_production = 500000.0
    prob = om.Problem()

    # Increase commodity sell price to get positive NPV
    npv_finance_inputs_positive = npv_finance_inputs.copy()
    npv_finance_inputs_positive["commodity_sell_price"] = 0.15

    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": npv_finance_inputs_positive},
    }
    pf = NumpyFinancialNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )

    ivc = om.IndepVarComp()
    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [1.0] * 30, units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("npv", pf, promotes=["*"])
    prob.setup()

    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"npv.{variable}", cost, units=units)

    prob.run_model()

    with subtests.test("Sell price"):
        assert (
            pytest.approx(
                prob.get_val("npv.sell_price_electricity_no1", units="USD/(kW*h)"), rel=1e-6
            )
            == npv_finance_inputs_positive["commodity_sell_price"]
        )

    with subtests.test("NPV positive"):
        npv_value = prob.get_val("npv.NPV_electricity_no1", units="USD")[0]
        assert pytest.approx(npv_value, rel=1e-6) == 3597582813.8071656


def _build_npv_problem(npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict):
    """Build and run an NPV problem with the given finance inputs."""
    mean_hourly_production = 500000.0
    prob = om.Problem()

    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": npv_finance_inputs},
    }
    pf = NumpyFinancialNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )

    ivc = om.IndepVarComp()
    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [1.0] * 30, units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("npv", pf, promotes=["*"])
    prob.setup()

    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"npv.{variable}", cost, units=units)

    prob.run_model()
    return prob


@pytest.mark.unit
def test_inflation_rate_defaults_to_zero(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    """Omitting inflation_rate should reproduce the baseline NPV (nominal-rate behavior)."""
    inputs_no_inflation = npv_finance_inputs.copy()
    inputs_with_zero_inflation = npv_finance_inputs.copy()
    inputs_with_zero_inflation["inflation_rate"] = 0.0

    prob_default = _build_npv_problem(
        inputs_no_inflation, fake_filtered_tech_config, fake_cost_dict
    )
    prob_explicit_zero = _build_npv_problem(
        inputs_with_zero_inflation, fake_filtered_tech_config, fake_cost_dict
    )

    npv_default = prob_default.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_explicit_zero = prob_explicit_zero.get_val("npv.NPV_electricity_no1", units="USD")[0]

    with subtests.test("Default inflation_rate matches baseline NPV"):
        assert pytest.approx(npv_default, rel=1e-6) == -1352263704.120

    with subtests.test("Explicit inflation_rate=0 matches default"):
        assert pytest.approx(npv_explicit_zero, rel=1e-12) == npv_default


@pytest.mark.unit
def test_inflation_rate_combines_via_fisher_equation(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    """Real and inflation rates should combine via the Fisher equation:
    (1 + r_nominal) = (1 + r_real) * (1 + inflation), matching ProFAST."""
    # Real discount rate 0.05 + inflation 0.04 should give the same NPV as a
    # nominal rate of (1.05 * 1.04 - 1) = 0.092, NOT 0.09 (the additive form).
    nominal_inputs = npv_finance_inputs.copy()
    nominal_inputs["discount_rate"] = 1.05 * 1.04 - 1.0  # 0.092

    split_inputs = npv_finance_inputs.copy()
    split_inputs["discount_rate"] = 0.05
    split_inputs["inflation_rate"] = 0.04

    inflation_only_inputs = npv_finance_inputs.copy()
    inflation_only_inputs["discount_rate"] = 0.0
    inflation_only_inputs["inflation_rate"] = 0.09

    inflation_only_nominal_inputs = npv_finance_inputs.copy()
    inflation_only_nominal_inputs["discount_rate"] = 0.09

    prob_nominal = _build_npv_problem(nominal_inputs, fake_filtered_tech_config, fake_cost_dict)
    prob_split = _build_npv_problem(split_inputs, fake_filtered_tech_config, fake_cost_dict)
    prob_inflation_only = _build_npv_problem(
        inflation_only_inputs, fake_filtered_tech_config, fake_cost_dict
    )
    prob_inflation_only_nominal = _build_npv_problem(
        inflation_only_nominal_inputs, fake_filtered_tech_config, fake_cost_dict
    )

    npv_nominal = prob_nominal.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_split = prob_split.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_inflation_only = prob_inflation_only.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_inflation_only_nominal = prob_inflation_only_nominal.get_val(
        "npv.NPV_electricity_no1", units="USD"
    )[0]

    with subtests.test("Real + inflation matches Fisher-equivalent nominal"):
        assert pytest.approx(npv_split, rel=1e-12) == npv_nominal

    with subtests.test("Inflation-only matches equivalent nominal (real=0)"):
        # With discount_rate=0, (1+0)*(1+pi)-1 = pi, so this should match a
        # nominal rate equal to the inflation rate exactly.
        assert pytest.approx(npv_inflation_only, rel=1e-12) == npv_inflation_only_nominal


@pytest.mark.unit
def test_inflation_rate_validator_rejects_out_of_range():
    """inflation_rate must be in [0, 1]."""
    with pytest.raises(ValueError, match="inflation_rate"):
        NumpyFinancialNPVFinanceConfig.from_dict(
            {
                "plant_life": 30,
                "discount_rate": 0.05,
                "inflation_rate": -0.01,
                "commodity_sell_price_units": "USD/(kW*h)",
            }
        )

    with pytest.raises(ValueError, match="inflation_rate"):
        NumpyFinancialNPVFinanceConfig.from_dict(
            {
                "plant_life": 30,
                "discount_rate": 0.05,
                "inflation_rate": 1.5,
                "commodity_sell_price_units": "USD/(kW*h)",
            }
        )
