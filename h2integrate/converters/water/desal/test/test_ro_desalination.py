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
