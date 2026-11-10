import numpy as np
import pytest
import openmdao.api as om

from h2integrate.converters.paper_mill.paper_mill import (
    PaperMillCostModel,
    PaperMillPerformanceModel,
)


N_TIMESTEPS = 24
PLANT_CAPACITY_MTPY = 8760.0  # 1 t/h of paper at full capacity
CAPACITY_FACTOR = 0.9
PLANT_LIFE = 30


@pytest.fixture
def plant_config():
    return {
        "plant": {"plant_life": PLANT_LIFE, "simulation": {"n_timesteps": N_TIMESTEPS, "dt": 3600}}
    }


@pytest.fixture
def tech_config():
    return {
        "model_inputs": {
            "shared_parameters": {"plant_capacity_mtpy": PLANT_CAPACITY_MTPY},
            "performance_parameters": {"capacity_factor": CAPACITY_FACTOR},
            "cost_parameters": {
                "installation_time": 24,
                "inflation_rate": 0.0,
                "operational_year": 2030,
            },
        }
    }


def run_component(component_class, plant_config, tech_config, **values):
    prob = om.Problem()
    comp = component_class(plant_config=plant_config, tech_config=tech_config, driver_config={})
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    for name, value in values.items():
        prob.set_val(name, value)
    prob.run_model()
    return prob


@pytest.mark.unit
def test_paper_mill_performance(subtests, plant_config, tech_config):
    prob = run_component(PaperMillPerformanceModel, plant_config, tech_config)
    paper_rate = 0.9  # t/h

    with subtests.test("Paper production"):
        np.testing.assert_allclose(prob.get_val("paper_out", units="t/h"), paper_rate)
        assert prob.get_val("rated_paper_production", units="t/h") == pytest.approx(1.0)
        assert prob.get_val("total_paper_produced", units="t") == pytest.approx(
            paper_rate * N_TIMESTEPS
        )
        np.testing.assert_allclose(
            prob.get_val("annual_paper_produced", units="t/year"),
            np.full(PLANT_LIFE, PLANT_CAPACITY_MTPY * CAPACITY_FACTOR),
        )
        np.testing.assert_allclose(prob.get_val("capacity_factor"), CAPACITY_FACTOR)

    with subtests.test("Lignin and pulp co-products use the default yields"):
        np.testing.assert_allclose(prob.get_val("lignin_out", units="kg/h"), 0.06 * 1000 * 0.9)
        assert prob.get_val("total_lignin_produced", units="kg") == pytest.approx(
            0.06 * 1000 * 0.9 * N_TIMESTEPS
        )
        np.testing.assert_allclose(prob.get_val("pulp_out", units="t/h"), 1.1 * 0.9)
        assert prob.get_val("annual_pulp_out_produced", units="t/year") == pytest.approx(
            1.1 * PLANT_CAPACITY_MTPY * CAPACITY_FACTOR
        )

    with subtests.test("Feedstock consumption scales with paper production"):
        consumption_per_t = {
            "wood_consumed": (0.225, "t/h"),
            "water_consumed": (40693, "kg/h"),
            "calcium_carbonate_consumed": (240, "kg/h"),
            "sodium_sulfide_consumed": (16.5, "kg/h"),
            "sodium_hydroxide_consumed": (3.5, "kg/h"),
            "chlorine_dioxide_consumed": (2, "kg/h"),
            "hydrogen_peroxide_consumed": (0.5, "kg/h"),
            "magnesium_sulfate_consumed": (0.2, "kg/h"),
            "oxygen_consumed": (2.25, "kg/h"),
        }
        for name, (per_t, units) in consumption_per_t.items():
            np.testing.assert_allclose(prob.get_val(name, units=units), per_t * paper_rate)


@pytest.mark.unit
def test_paper_mill_performance_capacity_input(plant_config, tech_config):
    prob = run_component(
        PaperMillPerformanceModel,
        plant_config,
        tech_config,
        plant_capacity_mtpy=PLANT_CAPACITY_MTPY / 2,
    )

    np.testing.assert_allclose(prob.get_val("paper_out", units="t/h"), 0.45)
    assert prob.get_val("rated_paper_production", units="t/h") == pytest.approx(0.5)


@pytest.mark.unit
def test_paper_mill_cost(subtests, plant_config, tech_config):
    prob = run_component(PaperMillCostModel, plant_config, tech_config)
    # Default consumables, water disposal, and electricity costs per tonne of paper
    variable_cost_per_t = 213.767018

    with subtests.test("CapEx"):
        assert prob.get_val("CapEx", units="USD") == pytest.approx(2500 * PLANT_CAPACITY_MTPY)

    with subtests.test("Fixed OpEx includes property tax and insurance"):
        assert prob.get_val("OpEx", units="USD/year") == pytest.approx(
            (370 + 0.02 * 2500) * PLANT_CAPACITY_MTPY
        )

    with subtests.test("Variable OpEx"):
        np.testing.assert_allclose(
            prob.get_val("VarOpEx", units="USD/year"),
            variable_cost_per_t * PLANT_CAPACITY_MTPY,
        )

    with subtests.test("Cost year"):
        assert prob.get_val("cost_year") == 2023


@pytest.mark.unit
def test_paper_mill_cost_transport_cost(plant_config, tech_config):
    baseline = run_component(PaperMillCostModel, plant_config, tech_config)
    tech_config["model_inputs"]["cost_parameters"]["wood_transport_cost"] = 10.0
    with_transport = run_component(PaperMillCostModel, plant_config, tech_config)

    np.testing.assert_allclose(
        with_transport.get_val("VarOpEx", units="USD/year")
        - baseline.get_val("VarOpEx", units="USD/year"),
        PLANT_CAPACITY_MTPY * 0.225 * 10.0,
    )


@pytest.mark.unit
def test_paper_mill_cost_rejects_other_cost_years(plant_config, tech_config):
    tech_config["model_inputs"]["cost_parameters"]["cost_year"] = 2020

    with pytest.raises(ValueError, match="cost_year"):
        run_component(PaperMillCostModel, plant_config, tech_config)
