import numpy as np
import pytest
import openmdao.api as om

from h2integrate.converters.saf.saf import SAFCostModel, SAFPerformanceModel


N_TIMESTEPS = 4
PLANT_CAPACITY_MTPY = 8760.0  # 1 t/h of SAF at full capacity
CAPACITY_FACTOR = 0.5
LIGNIN_PER_T_SAF = 1650.0  # kg lignin/t SAF, the model default
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
def test_saf_performance_limited_by_lignin_and_capacity(subtests, plant_config, tech_config):
    # Enough lignin for 0, 0.25, 0.5, and 1.0 t/h of SAF; capacity limits output to 0.5 t/h
    lignin_in = np.array([0.0, 0.25, 0.5, 1.0]) * LIGNIN_PER_T_SAF
    prob = run_component(SAFPerformanceModel, plant_config, tech_config, lignin_in=lignin_in)
    expected_saf = np.array([0.0, 0.25, 0.5, 0.5])

    with subtests.test("SAF output"):
        np.testing.assert_allclose(prob.get_val("saf_out", units="t/h"), expected_saf)
        assert prob.get_val("rated_saf_production", units="t/h") == pytest.approx(1.0)
        assert prob.get_val("total_saf_produced", units="t") == pytest.approx(expected_saf.sum())
        np.testing.assert_allclose(
            prob.get_val("annual_saf_produced", units="t/year"),
            expected_saf.sum() * 8760 / N_TIMESTEPS,
        )

    with subtests.test("Lignin consumption"):
        np.testing.assert_allclose(
            prob.get_val("lignin_consumed", units="kg/h"), expected_saf * LIGNIN_PER_T_SAF
        )
        assert prob.get_val("total_lignin_consumed", units="kg") == pytest.approx(
            expected_saf.sum() * LIGNIN_PER_T_SAF
        )
        assert prob.get_val("annual_lignin_consumed", units="kg/year") == pytest.approx(
            expected_saf.sum() * LIGNIN_PER_T_SAF * 8760 / N_TIMESTEPS
        )


@pytest.mark.unit
def test_saf_performance_without_lignin(plant_config, tech_config):
    prob = run_component(SAFPerformanceModel, plant_config, tech_config)

    np.testing.assert_allclose(prob.get_val("saf_out", units="t/h"), 0.0)
    np.testing.assert_allclose(prob.get_val("lignin_consumed", units="kg/h"), 0.0)


@pytest.mark.unit
def test_saf_cost(subtests, plant_config, tech_config):
    prob = run_component(SAFCostModel, plant_config, tech_config)
    # Default consumables and electricity costs per tonne of SAF
    variable_cost_per_t = 6668.320441

    with subtests.test("CapEx"):
        assert prob.get_val("CapEx", units="USD") == pytest.approx(5570 * PLANT_CAPACITY_MTPY)

    with subtests.test("Fixed OpEx includes property tax and insurance"):
        assert prob.get_val("OpEx", units="USD/year") == pytest.approx(
            (390 + 0.02 * 5570) * PLANT_CAPACITY_MTPY
        )

    with subtests.test("Variable OpEx"):
        np.testing.assert_allclose(
            prob.get_val("VarOpEx", units="USD/year"),
            variable_cost_per_t * PLANT_CAPACITY_MTPY,
        )


@pytest.mark.unit
def test_saf_cost_scales_with_capacity_input(plant_config, tech_config):
    prob = run_component(
        SAFCostModel, plant_config, tech_config, plant_capacity_mtpy=2 * PLANT_CAPACITY_MTPY
    )

    assert prob.get_val("CapEx", units="USD") == pytest.approx(5570 * 2 * PLANT_CAPACITY_MTPY)
