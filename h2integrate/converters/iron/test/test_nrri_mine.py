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
        "taconite_pellet_type": "std",
    }
    tech_config = {
        "model_inputs": {
            "shared_parameters": shared_params,
            "performance_parameters": {
                "max_ore_production_rate_tonnes_per_hr": (7457805 * 0.98 * 1.016)
                / 8760,  # convert from WLT/yr to LT/yr to t/yr and then hourly,
            },
            "cost_parameters": {
                "cost_year": 2025,
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
    prob = om.Problem()
    iron_ore_cost = NRRIIronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_cost, promotes=["*"])
    prob.setup()

    prob.set_val("comp.annual_iron_ore_produced", [7457805 * 1.016], units="t/yr")
    prob.set_val("comp.raw_ore", [1e6] * 8760, units="t/h")

    prob.run_model()

    # check total opex for year 1
    with subtests.test("total_opex"):
        total_opex = prob.get_val("comp.OpEx", units="USD/yr")
        assert total_opex == pytest.approx(7457805 * 15.3, rel=1e-3)


@pytest.mark.regression
def test_iron_mine_cost_outputs(plant_config, driver_config, iron_ore_config_martin_om, subtests):
    iron_ore_config_martin_om["model_inputs"]["shared_parameters"]["mine"] = "United"
    prob = om.Problem()
    iron_ore_cost = NRRIIronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_cost, promotes=["*"])
    prob.setup()

    prob.set_val("comp.annual_iron_ore_produced", [7457805 * 1.016], units="t/yr")
    prob.set_val("comp.raw_ore", [10] * 8760, units="t/h")

    prob.run_model()

    # check total opex for year 1
    with subtests.test("total_opex"):
        total_opex = prob.get_val("comp.OpEx", units="USD/yr")
        assert total_opex == pytest.approx(87600 * 3.72 / 1.016, rel=1e-3)
