import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.finances.profast_lco import ProFastLCO


@fixture
def profast_inputs_no1():
    params = {
        "analysis_start_year": 2030, #changed
        "installation_time": 24, #24 months? 
        "inflation_rate": 0.0, 
        "discount_rate": 0.0948,
        "debt_equity_ratio": 1.72,
        "property_tax_and_insurance": 0.015, #should we use this value?
        "total_income_tax_rate": 0.2574, #should we use this value?
        "capital_gains_tax_rate": 0.15, #should we use this value?
        "sales_tax_rate": 0.00,
        "debt_interest_rate": 0.046, #should we use this value?
        "debt_type": "Revolving debt",
        "loan_period_if_used": 0,
        "cash_onhand_months": 1,
        "admin_expense": 0.00,
    }
    cap_items = {"depr_type": "MACRS", "depr_period": 7, "refurb": [0.0]}
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
        "capex_adjusted_wind": 0,
        "opex_adjusted_wind": 0,
        "varopex_adjusted_wind": [0.0] * 0,
        "capex_adjusted_solar": 0,
        "opex_adjusted_solar": 0,
        "varopex_adjusted_solar": [0.0] * 0,
        "capex_adjusted_battery": 0,
        "opex_adjusted_battery": 0,
        "varopex_adjusted_battery": [0.0] * 00,
        "capex_adjusted_natural_gas": 0,
        "opex_adjusted_natural_gas": 0,
        "varopex_adjusted_natural_gas": [0] * 00,
    }
    return fake_costs


@pytest.mark.regression
def test_profast_comp(profast_inputs_no1, fake_filtered_tech_config, fake_cost_dict, subtests):
    mean_hourly_production = 34246.6 # ton/hr
    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 40,
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

    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [0.9] * plant_config["plant"]["plant_life"], units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("pf", pf, promotes=["rated_electricity_production", "capacity_factor"])
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


@pytest.mark.regression
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
    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [1.0] * plant_config["plant"]["plant_life"], units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("pf", pf, promotes=["rated_electricity_production", "capacity_factor"])
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
