import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.iron.nrri_iron_mine import IronMinePerformanceComponent


@fixture
def iron_ore_config_martin_om():
    shared_params = {
        "mine": "Tilden",
        "max_ore_production_rate_tonnes_per_hr": (7457805 * 0.98 * 1.016)
        / 8760,  # convert from WLT/yr to LT/yr to t/yr and then hourly,
    }
    tech_config = {
        "model_inputs": {
            "shared_parameters": shared_params,
        }
    }
    return tech_config


@pytest.mark.regression
def test_iron_mine_performance_outputs(
    plant_config, driver_config, iron_ore_config_martin_om, subtests
):
    prob = om.Problem()
    iron_ore_perf = IronMinePerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_perf, promotes=["*"])
    prob.setup()

    annual_electricity = 85795.22689
    annual_fuel = 2134.768277
    ore_rated_capacity = 7457805 * 0.98 * 1.016

    prob.set_val("comp.electricity_in", [annual_electricity] * 8760, units="kW")
    prob.set_val("comp.fuel_in", [annual_fuel] * 8760, units="MMBtu/h")
    prob.set_val("comp.iron_ore_command_value", [ore_rated_capacity], units="t/h")

    prob.run_model()
    commodity_rate_units = "t/h"
    int(plant_config["plant"]["plant_life"])
    int(plant_config["plant"]["simulation"]["n_timesteps"])

    # check pellet production
    with subtests.test("iron_ore_out"):
        iron_ore_out = prob.get_val("comp.iron_ore_out", units=commodity_rate_units)
        assert np.sum(iron_ore_out) == pytest.approx(7457805 * 0.98 * 1.016, rel=1e-3)

    with subtests.test("pelletization elec"):
        pel_elec = prob.get_val("comp.pelletization_electricity", units="kW")
        assert np.sum(pel_elec) == pytest.approx(23.62080378 * 7457805 * 0.98, rel=1e-3)
