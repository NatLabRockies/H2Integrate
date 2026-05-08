import numpy as np
import pytest
import openmdao.api as om

from h2integrate.finances.finances import AdjustedCapacityFactorComp


@pytest.fixture
def plant_config(n_timesteps):
    plant = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": n_timesteps,
            },
        },
    }
    return plant


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [8760])
def test_adjusted_cf_comp(plant_config, subtests):
    rng = np.random.default_rng(seed=0)
    electricity_input = rng.random(8760) * 1e3

    prob = om.Problem()
    comp = AdjustedCapacityFactorComp(plant_config=plant_config, commodity_type="electricity")
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    ivc = om.IndepVarComp()
    ivc.add_output("electricity_produced", val=np.zeros(8760), units="kW")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()
    prob.set_val("ivc.electricity_produced", val=electricity_input, units="kW")
    prob.run_model()

    with subtests.test("Check rated_electricity_production calc"):
        assert (
            pytest.approx(
                prob.model.get_val("comp.rated_electricity_production", units="kW"), rel=1e-6
            )
            == electricity_input.mean()
        )

    with subtests.test("Check capacity factor"):
        assert np.all(prob.model.get_val("comp.capacity_factor", units="unitless")) == 1.0

    with subtests.test("Capacity factor length"):
        assert len(prob.model.get_val("comp.capacity_factor", units="unitless")) == 30
