import pytest
import openmdao.api as om

from h2integrate.converters.hydrogen.custom_electrolyzer_cost_model import (
    CustomElectrolyzerCostModel,
)


def test_custom_electrolyzer_cost_model(subtests):
    capex_usd_per_kw = 10.0
    opex_usd_per_kw = 5.0

    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": {
                "capex_USD_per_kW": capex_usd_per_kw,  # dummy number
                "fixed_om_USD_per_kW_per_year": opex_usd_per_kw,  # dummy number
                "cost_year": 2022,
            },
        }
    }

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,  # Default number of timesteps for the simulation
            },
        },
    }

    rated_power_kW = 1000.0
    prob = om.Problem()
    comp = CustomElectrolyzerCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("custom_elec_cost", comp)
    prob.setup()
    prob.set_val("custom_elec_cost.electrolyzer_size_mw", rated_power_kW, units="kW")

    prob.run_model()

    expected_outputs = {
        "CapEx": [rated_power_kW * capex_usd_per_kw],
        "OpEx": [rated_power_kW * opex_usd_per_kw],
    }

    for out, expected in expected_outputs.items():
        with subtests.test(out):
            val = prob.get_val(f"custom_elec_cost.{out}")
            assert pytest.approx(val, rel=1e-6) == expected[0]
