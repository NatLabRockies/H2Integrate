import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.finances.profast_lco import ProFastLCO


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
    model_inputs = {"params": params, "capital_items": cap_items}

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


def test_profast_comp(profast_inputs_no1, fake_filtered_tech_config, fake_cost_dict, subtests):
    mean_hourly_production = 500000.0
    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": profast_inputs_no1},
    }
    pf = ProFastLCO(
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

    lcoe = prob.get_val("pf.LCOE_no1", units="USD/(MW*h)")
    price = prob.get_val("pf.price_electricity_no1", units="USD/(MW*h)")

    wacc = prob.get_val("pf.wacc_electricity_no1", units="percent")
    crf = prob.get_val("pf.crf_electricity_no1", units="percent")
    profit_index = prob.get_val("pf.profit_index_electricity_no1", units="unitless")
    irr = prob.get_val("pf.irr_electricity_no1", units="percent")
    ipp = prob.get_val("pf.investor_payback_period_electricity_no1", units="yr")

    lcoe_breakdown = prob.get_val("pf.LCOE_no1_breakdown")

    with subtests.test("LCOE"):
        assert pytest.approx(lcoe[0], rel=1e-6) == 63.8181779

    with subtests.test("WACC"):
        assert pytest.approx(wacc[0], rel=1e-6) == 0.056453864

    with subtests.test("CRF"):
        assert pytest.approx(crf[0], rel=1e-6) == 0.0674704169

    with subtests.test("Profit Index"):
        assert pytest.approx(profit_index[0], rel=1e-6) == 2.12026237778

    with subtests.test("IRR"):
        assert pytest.approx(irr[0], rel=1e-6) == 0.0948

    with subtests.test("Investor payback period"):
        assert pytest.approx(ipp[0], rel=1e-6) == 8

    with subtests.test("LCOE == price"):
        assert pytest.approx(lcoe, rel=1e-6) == price

    with subtests.test("LCOE breakdown total"):
        assert pytest.approx(lcoe_breakdown["LCOE: Total ($/kWh)"] * 1e3, rel=1e-6) == lcoe


def test_profast_comp_coproduct(
    profast_inputs_no1, fake_filtered_tech_config, fake_cost_dict, subtests
):
    mean_hourly_production = 500000.0  # kW*h
    grid_sell_price = 63.8181779 / 1e3  # USD/(kW*h)
    wind_sold_USD = [-1 * mean_hourly_production * 8760 * grid_sell_price] * 30
    fake_cost_dict.update({"varopex_adjusted_wind": wind_sold_USD})

    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": profast_inputs_no1},
    }
    pf = ProFastLCO(
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

    lcoe = prob.get_val("pf.LCOE_no1", units="USD/(MW*h)")
    price = prob.get_val("pf.price_electricity_no1", units="USD/(MW*h)")

    wacc = prob.get_val("pf.wacc_electricity_no1", units="percent")
    crf = prob.get_val("pf.crf_electricity_no1", units="percent")
    profit_index = prob.get_val("pf.profit_index_electricity_no1", units="unitless")
    irr = prob.get_val("pf.irr_electricity_no1", units="percent")
    ipp = prob.get_val("pf.investor_payback_period_electricity_no1", units="yr")

    lcoe_breakdown = prob.get_val("pf.LCOE_no1_breakdown")

    with subtests.test("LCOE"):
        assert pytest.approx(lcoe[0], abs=1e-6) == 0

    with subtests.test("WACC"):
        assert pytest.approx(wacc[0], rel=1e-6) == 0.056453864

    with subtests.test("CRF"):
        assert pytest.approx(crf[0], rel=1e-6) == 0.0674704169

    with subtests.test("Profit Index"):
        assert pytest.approx(profit_index[0], rel=1e-6) == 2.12026237778

    with subtests.test("IRR"):
        assert pytest.approx(irr[0], rel=1e-6) == 0.0948

    with subtests.test("Investor payback period"):
        assert pytest.approx(ipp[0], rel=1e-6) == 8

    with subtests.test("LCOE == price"):
        assert pytest.approx(lcoe, rel=1e-6) == price

    with subtests.test("LCOE breakdown total"):
        assert pytest.approx(lcoe_breakdown["LCOE: Total ($/kWh)"] * 1e3, rel=1e-6) == lcoe
