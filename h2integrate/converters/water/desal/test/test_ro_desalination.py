import numpy as np
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.converters.water.desal.desalination import (
    ReverseOsmosisCostModel,
    ReverseOsmosisPerformanceModel,
)


@fixture
def plant_config():
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
        },
    }

    return {"plant": plant}


def test_brackish_desal_outputs(plant_config, subtests):
    tech_config = {
        "model_inputs": {
            "performance_parameters": {
                "freshwater_kg_per_hour": 10000,
                "salinity": "brackish",
                "freshwater_density": 997,
            },
        }
    }

    prob = om.Problem()
    comp = ReverseOsmosisPerformanceModel(plant_config=plant_config, tech_config=tech_config)
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    commodity = "water"
    commodity_amount_units = "m**3"
    commodity_rate_units = "m**3/h"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    # Check that replacement schedule is between 0 and 1
    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    # Check that capacity factor is between 0 and 1 with units of "unitless"
    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") <= 1)

    # Check that capacity factor is between 1 and 100 with units of "percent"
    with subtests.test("1 <= capacity_factor (percent) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("comp.capacity_factor", units="unitless")) == plant_life

    # Test that rated commodity production is greater than zero
    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units) > 0
        )

    with subtests.test(f"rated_{commodity}_production length"):
        assert (
            len(prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units)) == 1
        )

    # Test that total commodity production is greater than zero
    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units) > 0
        )
    with subtests.test(f"total_{commodity}_produced length"):
        assert (
            len(prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units)) == 1
        )

    # Test that annual commodity production is greater than zero
    with subtests.test(f"annual_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr")
            > 0
        )

    with subtests.test(f"annual_{commodity}_produced[1:] == annual_{commodity}_produced[0]"):
        annual_production = prob.get_val(
            f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"annual_{commodity}_produced length"):
        assert len(annual_production) == plant_life

    # Test that commodity output has some values greater than zero
    with subtests.test(f"Some of {commodity}_out > 0"):
        assert np.any(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units) > 0)

    with subtests.test(f"{commodity}_out length"):
        assert len(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units)) == n_timesteps

    # Test default values
    with subtests.test("operational_life default value"):
        assert prob.get_val("comp.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


def test_brackish_performance(plant_config, subtests):
    tech_config = {
        "model_inputs": {
            "performance_parameters": {
                "freshwater_kg_per_hour": 10000,
                "salinity": "brackish",
                "freshwater_density": 997,
            },
        }
    }

    prob = om.Problem()
    comp = ReverseOsmosisPerformanceModel(plant_config=plant_config, tech_config=tech_config)
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("fresh water"):
        assert prob["water_out"] == approx(10.03, rel=1e-5)
    with subtests.test("mass"):
        assert prob["mass"] == approx(3477.43, rel=1e-3)
    with subtests.test("footprint"):
        assert prob["footprint"] == approx(4.68, rel=1e-3)
    with subtests.test("feedwater"):
        assert prob["feedwater"] == approx(13.37, rel=1e-3)
    with subtests.test("electricity"):
        assert prob["electricity_in"] == approx(15.04, rel=1e-3)


def test_seawater_performance(plant_config, subtests):
    tech_config = {
        "model_inputs": {
            "performance_parameters": {
                "freshwater_kg_per_hour": 10000,
                "salinity": "seawater",
                "freshwater_density": 997,
            },
        }
    }

    prob = om.Problem()
    comp = ReverseOsmosisPerformanceModel(plant_config=plant_config, tech_config=tech_config)
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("fresh water"):
        assert prob["water_out"] == approx(10.03, rel=1e-5)
    with subtests.test("mass"):
        assert prob["mass"] == approx(3477.43, rel=1e-3)
    with subtests.test("footprint"):
        assert prob["footprint"] == approx(4.68, rel=1e-3)
    with subtests.test("feedwater"):
        assert prob["feedwater"] == approx(20.06, rel=1e-5)
    with subtests.test("electricity"):
        assert prob["electricity_in"] == approx(40.12, rel=1e-5)


def test_ro_desalination_cost(subtests):
    tech_config = {
        "model_inputs": {
            "cost_parameters": {
                "freshwater_kg_per_hour": 10000,
                "freshwater_density": 997,
            },
        }
    }

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }

    prob = om.Problem()
    comp = ReverseOsmosisCostModel(tech_config=tech_config, plant_config=plant_config)
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("capex"):
        assert prob["CapEx"] == approx(91372, rel=1e-2)
    with subtests.test("opex"):
        assert prob["OpEx"] == approx(13447, rel=1e-2)
