import numpy as np
import pytest
import openmdao.api as om
from pytest import approx

from h2integrate.converters.hydrogen.wombat_model import WOMBATElectrolyzerModel


def test_wombat_model_outputs(subtests):
    prob = om.Problem()
    prob.model.add_subsystem(
        "wombat_model",
        WOMBATElectrolyzerModel(
            plant_config={
                "plant": {
                    "plant_life": 20,
                    "simulation": {
                        "n_timesteps": 8760,
                    },
                },
            },
            tech_config={
                "model_inputs": {
                    "shared_parameters": {
                        "location": "onshore",
                        "electrolyzer_capex": 1295,
                        "size_mode": "normal",
                        "n_clusters": 1,
                        "cluster_rating_MW": 40,
                        "eol_eff_percent_loss": 13,
                        "uptime_hours_until_eol": 80000.0,
                        "include_degradation_penalty": True,
                        "turndown_ratio": 0.1,
                        "library_path": "resource_files/wombat_library",
                        "cost_year": 2022,
                    },
                }
            },
        ),
        promotes=["*"],
    )
    prob.setup()
    prob.set_val("electricity_in", np.ones(8760) * 40.0, units="MW")
    prob.run_model()

    with subtests.test("hydrogen_out"):
        assert np.linalg.norm(prob["hydrogen_out"]) == approx(72653.05815087, rel=1e-2)
    with subtests.test("total_hydrogen_produced"):
        assert prob["total_hydrogen_produced"] == approx(6777348.33570215, rel=1e-2)
    with subtests.test("efficiency"):
        assert prob["efficiency"] == approx(0.76733639, rel=1e-2)
    with subtests.test("rated_h2_production_kg_pr_hr"):
        assert prob["rated_h2_production_kg_pr_hr"] == approx(784.3544736, rel=1e-2)
    with subtests.test("capacity_factor"):
        assert prob["capacity_factor"] == approx(0.75637315, rel=1e-2)
    with subtests.test("CapEx"):
        assert prob["CapEx"] == approx(51800000.0, rel=1e-2)
    with subtests.test("OpEx"):
        assert prob["OpEx"] == approx(1004502.975183, rel=1e-2)
    with subtests.test("percent_hydrogen_lost"):
        assert prob["percent_hydrogen_lost"] == approx(1.50371, rel=1e-2)
    with subtests.test("electrolyzer_availability"):
        assert prob["electrolyzer_availability"] == approx(0.993379, rel=1e-2)


def test_wombat_error(subtests):
    prob = om.Problem()
    prob.model.add_subsystem(
        "wombat_model",
        WOMBATElectrolyzerModel(
            plant_config={
                "plant": {
                    "plant_life": 20,
                    "simulation": {
                        "n_timesteps": 8760,
                    },
                },
            },
            tech_config={
                "model_inputs": {
                    "shared_parameters": {
                        "location": "onshore",
                        "electrolyzer_capex": 1295,
                        "size_mode": "normal",
                        "n_clusters": 0.75,
                        "cluster_rating_MW": 40,
                        "eol_eff_percent_loss": 13,
                        "uptime_hours_until_eol": 80000.0,
                        "include_degradation_penalty": True,
                        "turndown_ratio": 0.1,
                        "library_path": "resource_files/wombat_library",
                        "cost_year": 2022,
                    },
                }
            },
        ),
        promotes=["*"],
    )
    prob.setup()
    prob.set_val("electricity_in", np.ones(8760) * 40.0, units="MW")

    with pytest.raises(ValueError, match="Electrolyzer rating .* does not match the product of"):
        prob.run_model()
