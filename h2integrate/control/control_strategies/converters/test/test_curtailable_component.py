import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.control.control_strategies.converters.curtailable_component import (
    CurtailableComponentModel,
)


@fixture
def plant_config_base():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
                "timezone": 0,
                "start_time": "01/01/2000 00:00:00",
            },
        }
    }

    return plant_config


@pytest.mark.unit
def test_curtailable_component(plant_config_base, subtests):
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_out", val=20, shape=8760, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="hydrogen_command_value", val=10, shape=8760, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "comp",
        CurtailableComponentModel(
            plant_config=plant_config_base,
            commodity="hydrogen",
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    with subtests.test("modulated output"):
        assert np.all(prob.get_val("comp.modulated_hydrogen_out", units="kg/h") == 10)
