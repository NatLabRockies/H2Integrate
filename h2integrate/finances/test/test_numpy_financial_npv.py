import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.finances.numpy_financial_npv import NumpyFinancialNPV


@fixture
def npv_finance_inputs():
    npv_dict = {
        "discount_rate": 0.09,
        "commodity_sell_price": 0.04,
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
