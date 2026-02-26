import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.transporters.generic_transporter import GenericTransporterPerformanceModel


@fixture
def plant_config():
    plant_dict = {
        "plant": {
            "plant_life": 30,
            "simulation": {"n_timesteps": 8760, "dt": 3600},
        }
    }
    return plant_dict


@pytest.mark.regression
def test_generic_transporter_in_out(plant_config, subtests):
    commodities_and_units = {
        "postassium": "kg/h",
        "heat": "MMBtu/h",
        "milk": "galUS/h",
        "sugar": "cup/h",
        "butter": "tbsp/h",
    }

    commodity_in_profile = np.full(8760, 100.0)
    for commodity, commodity_rate_units in commodities_and_units.items():
        transporter_config = {
            "model_inputs": {
                "performance_parameters": {
                    "commodity": commodity,
                    "commodity_rate_units": commodity_rate_units,
                }
            }
        }

        prob = om.Problem()
        comp = GenericTransporterPerformanceModel(
            plant_config=plant_config, tech_config=transporter_config, driver_config={}
        )
        prob.model.add_subsystem("comp", comp, promotes=["*"])

        ivc = om.IndepVarComp()
        ivc.add_output(f"{commodity}_in", val=commodity_in_profile, units=commodity_rate_units)
        prob.model.add_subsystem("ivc", ivc, promotes=["*"])

        prob.setup()

        prob.set_val(f"{commodity}_in", commodity_in_profile, units=commodity_rate_units)
        prob.run_model()

        with subtests.test(f"{commodity}_in == {commodity}_out"):
            assert pytest.approx(
                prob.get_val(f"{commodity}_in", units=commodity_rate_units), rel=1e-6
            ) == prob.get_val(f"{commodity}_out", units=commodity_rate_units)

        with subtests.test(f"{commodity}_in == commodity profile"):
            assert (
                pytest.approx(prob.get_val(f"{commodity}_in", units=commodity_rate_units), rel=1e-6)
                == commodity_in_profile
            )
