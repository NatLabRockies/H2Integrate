import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.finances.profast_npv import ProFastNPV


@fixture
def profast_inputs_no1():
    params = {
        "analysis_start_year": 2032,
        "installation_time": 36,
        "inflation_rate": 0.0,
        "discount_rate": 0.0948,
        "debt_equity_ratio": 1.72,
        "property_tax_and_insurance": 0.015,
        "total_income_tax_rate": 0.2574,
        "capital_gains_tax_rate": 0.15,
        "sales_tax_rate": 0.00,
        "debt_interest_rate": 0.046,
        "debt_type": "Revolving debt",
        "loan_period_if_used": 0,
        "cash_onhand_months": 1,
        "admin_expense": 0.00,
    }
    cap_items = {"depr_type": "MACRS", "depr_period": 5, "refurb": [0.0]}
    model_inputs = {
        "commodity_sell_price": 0.04,  # USD/kWh for electricity
        "params": params,
        "capital_items": cap_items,
    }

    return model_inputs


@fixture
def profast_inputs_no2():
    params = {
        "analysis_start_year": 2032,
        "installation_time": 36,
        "inflation_rate": 0.0,
        "discount_rate": 0.0615,
        "debt_equity_ratio": 2.82,
        "property_tax_and_insurance": 0.015,
        "total_income_tax_rate": 0.2574,
        "capital_gains_tax_rate": 0.15,
        "sales_tax_rate": 0.00,
        "debt_interest_rate": 0.0439,
        "debt_type": "Revolving debt",
        "loan_period_if_used": 0,
        "cash_onhand_months": 1,
        "admin_expense": 0.00,
    }
    cap_items = {"depr_type": "MACRS", "depr_period": 5, "refurb": [0.0]}

    model_inputs = {
        "commodity_sell_price": 0.07,  # USD/kWh for electricity
        "params": params,
        "capital_items": cap_items,
    }

    return model_inputs


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


def test_profast_npv_no1(profast_inputs_no1, fake_filtered_tech_config, fake_cost_dict, subtests):
    mean_hourly_production = 500000.0
    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": profast_inputs_no1},
    }
    pf = ProFastNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )
    ivc = om.IndepVarComp()
    ivc.add_output("total_electricity_produced", mean_hourly_production * 8760, units="kW*h/year")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("pf", pf, promotes=["total_electricity_produced"])
    prob.setup()
    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"pf.{variable}", cost, units=units)

    prob.run_model()

    with subtests.test("Sell price"):
        assert (
            pytest.approx(
                prob.get_val("pf.sell_price_electricity_no1", units="USD/(kW*h)"), rel=1e-6
            )
            == profast_inputs_no1["commodity_sell_price"]
        )

    with subtests.test("NPV"):
        assert (
            pytest.approx(prob.get_val("pf.NPV_electricity_no1", units="USD")[0], rel=1e-6)
            == -580179388.883
        )


def test_profast_npv_no1_change_sell_price(
    profast_inputs_no1, fake_filtered_tech_config, fake_cost_dict, subtests
):
    mean_hourly_production = 500000.0
    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": profast_inputs_no1},
    }
    pf = ProFastNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )

    pf2 = ProFastNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1_expensive",
    )

    ivc = om.IndepVarComp()
    ivc.add_output("total_electricity_produced", mean_hourly_production * 8760, units="kW*h/year")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("pf", pf, promotes=["total_electricity_produced"])
    prob.model.add_subsystem("pf2", pf2, promotes=["total_electricity_produced"])
    prob.setup()
    # set inputs for 'pf' with commodity sell price of 0.04 USD/(kW*h)
    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"pf.{variable}", cost, units=units)

    # set inputs for 'pf2' with commodity sell price of 0.07 USD/(kW*h)
    new_sell_price = 0.07
    prob.set_val("pf2.sell_price_electricity_no1_expensive", new_sell_price, units="USD/(kW*h)")
    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"pf2.{variable}", cost, units=units)

    prob.run_model()

    with subtests.test("Sell price for pf"):
        assert (
            pytest.approx(
                prob.get_val("pf.sell_price_electricity_no1", units="USD/(kW*h)"), rel=1e-6
            )
            == profast_inputs_no1["commodity_sell_price"]
        )

    with subtests.test("NPV with sell price of 0.04 USD/(kW*h)"):
        assert (
            pytest.approx(prob.get_val("pf.NPV_electricity_no1", units="USD")[0], rel=1e-6)
            == -580179388.883
        )

    with subtests.test("Sell price for pf2"):
        assert (
            pytest.approx(
                prob.get_val("pf2.sell_price_electricity_no1_expensive", units="USD/(kW*h)"),
                rel=1e-6,
            )
            == new_sell_price
        )

    with subtests.test("NPV is higher with higher commodity sell price"):
        assert (
            prob.get_val("pf2.NPV_electricity_no1_expensive", units="USD")
            > prob.get_val("pf.NPV_electricity_no1", units="USD")[0]
        )

    with subtests.test("NPV with sell price of 0.07 USD/(kW*h)"):
        assert (
            pytest.approx(
                prob.get_val("pf2.NPV_electricity_no1_expensive", units="USD")[0], rel=1e-6
            )
            == 150581030.887
        )


def test_profast_npv_no2(profast_inputs_no2, fake_filtered_tech_config, fake_cost_dict, subtests):
    mean_hourly_production = 500000.0
    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": profast_inputs_no2},
    }
    pf = ProFastNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no2",
    )
    ivc = om.IndepVarComp()
    ivc.add_output("total_electricity_produced", mean_hourly_production * 8760, units="kW*h/year")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("pf", pf, promotes=["total_electricity_produced"])
    prob.setup()
    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"pf.{variable}", cost, units=units)

    prob.run_model()

    with subtests.test("Sell price"):
        assert (
            pytest.approx(
                prob.get_val("pf.sell_price_electricity_no2", units="USD/(kW*h)"), rel=1e-6
            )
            == profast_inputs_no2["commodity_sell_price"]
        )

    with subtests.test("NPV"):
        assert (
            pytest.approx(prob.get_val("pf.NPV_electricity_no2", units="USD")[0], rel=1e-6)
            == 611288384.412
        )
