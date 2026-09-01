import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.iron.nrri_iron_mine import (
    NRRIIronMineCostComponent,
    NRRIIronMinePerformanceComponent,
)


@fixture
def iron_ore_config_martin_om():
    shared_params = {
        "mine": "Tilden",
    }
    tech_config = {
        "model_inputs": {
            "shared_parameters": shared_params,
            "performance_parameters": {
                "max_ore_production_rate_tonnes_per_hr": (7457805 * 0.98 * 1.016)
                / 8760,  # convert from WLT/yr to LT/yr to t/yr and then hourly,
            },
            "cost_parameters": {
                "cost_year": 2021,
                "taconite_pellet_type": "std",
            },
        }
    }
    return tech_config


@pytest.mark.unit
def test_iron_mine_performance_outputs(
    plant_config, driver_config, iron_ore_config_martin_om, subtests
):
    prob = om.Problem()
    iron_ore_perf = NRRIIronMinePerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_perf, promotes=["*"])
    prob.setup()

    hourly_electricity = 85795.22689
    hourly_fuel = 2134.768277
    hourly_diesel = 1e6
    ore_rated_capacity = 7457805 * 0.98 * 1.016

    prob.set_val("comp.electricity_in", [hourly_electricity] * 8760, units="kW")
    prob.set_val("comp.natural_gas_in", [hourly_fuel] * 8760, units="MMBtu/h")
    prob.set_val("comp.diesel_in", [hourly_diesel] * 8760, units="galUS/h")
    prob.set_val("comp.iron_ore_command_value", [ore_rated_capacity], units="t/h")

    prob.run_model()
    commodity_rate_units = "t/h"

    # check pellet production
    with subtests.test("iron_ore_out"):
        iron_ore_out = prob.get_val("comp.iron_ore_out", units=commodity_rate_units)
        # 0.98 is converting from WLT to LT, 1.016 is converting from LT to t
        assert np.sum(iron_ore_out) == pytest.approx(7457805 * 0.98 * 1.016, rel=1e-3)

    with subtests.test("pelletization elec"):
        pel_elec = prob.get_val("comp.pelletization_electricity", units="kW")
        assert np.sum(pel_elec) == pytest.approx(23.62080378 * 7457805 * 0.98, rel=1e-3)


@pytest.mark.regression
def test_iron_pellet_cost_outputs(plant_config, driver_config, iron_ore_config_martin_om, subtests):
    plant_config["finance_parameters"]["cost_adjustment_parameters"]["target_dollar_year"] = 2021
    prob = om.Problem()
    iron_ore_cost = NRRIIronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_cost, promotes=["*"])
    prob.setup()

    prob.set_val("comp.annual_iron_ore_produced", [7457805 * 1.016], units="t/yr")

    prob.run_model()

    with subtests.test("total_capex"):
        total_capex = prob.get_val("comp.CapEx", units="USD")
        assert total_capex == pytest.approx(1527719439.562, rel=1e-3)

    # check total opex for year 1
    with subtests.test("total_opex"):
        total_opex = prob.get_val("comp.OpEx", units="USD/yr")
        assert total_opex == pytest.approx(7457805.0 * 48.66003278, rel=1e-3)


@pytest.mark.regression
def test_iron_mine_cost_outputs(plant_config, driver_config, iron_ore_config_martin_om, subtests):
    iron_ore_config_martin_om["model_inputs"]["shared_parameters"]["mine"] = "United"
    iron_ore_config_martin_om["model_inputs"]["cost_parameters"]["taconite_pellet_type"] = "drg"
    plant_config["finance_parameters"]["cost_adjustment_parameters"]["target_dollar_year"] = 2021
    prob = om.Problem()
    iron_ore_cost = NRRIIronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_cost, promotes=["*"])
    prob.setup()

    prob.set_val("comp.annual_iron_ore_produced", [7457805 * 1.016], units="t/yr")

    prob.run_model()

    # check total opex for year 1
    with subtests.test("total_opex"):
        total_opex = prob.get_val("comp.OpEx", units="USD/yr")
        assert total_opex == pytest.approx(7457805.0 * 89.3661325, rel=1e-3)


@pytest.mark.regression
def test_adjusting_cost_year(plant_config, driver_config, iron_ore_config_martin_om, subtests):
    iron_ore_config_martin_om["model_inputs"]["shared_parameters"]["mine"] = "United"
    iron_ore_config_martin_om["model_inputs"]["cost_parameters"]["taconite_pellet_type"] = "drg"
    prob = om.Problem()
    iron_ore_cost = NRRIIronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_cost, promotes=["*"])
    prob.setup()

    prob.set_val("comp.annual_iron_ore_produced", [7457805 * 1.016], units="t/yr")

    prob.run_model()

    # check total opex for year 1
    with subtests.test("total_opex"):
        total_opex = prob.get_val("comp.OpEx", units="USD/yr")
        # greater than 2021 because the cost year is adjusted to 2022, which has a higher CPI
        assert total_opex == pytest.approx(719809158.0098612, rel=1e-3)
