import os

import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.utilities import load_yaml
from h2integrate.converters.wind.wind_plant_ard import ArdWindPlantModel


@fixture
def ard_config():
    wind_io_path = EXAMPLE_DIR / "xx_wind_ard" / "ard_inputs" / "windio.yaml"
    wind_io_dict = load_yaml(wind_io_path)
    ard_tech_dict = {
        "performance_parameters": {
            "ard_data_path": "./",
            "ard_system": {
                "system": "onshore_batch",
                "modeling_options": {
                    "windIO_plant": wind_io_dict,  # Path to windio file
                    "layout": {
                        "N_turbines": 9,
                        "N_substations": 1,
                        "spacing_primary": 7.0,
                        "spacing_secondary": 7.0,
                        "angle_orientation": 0.0,
                        "angle_skew": 0.0,
                    },
                    "aero": {
                        "return_turbine_output": False,
                    },
                    "floris": {
                        "peak_shaving_fraction": 0.2,
                        "peak_shaving_TI_threshold": 0.0,
                    },
                    "collection": {
                        "max_turbines_per_string": 8,
                        "solver_name": "highs",
                        "solver_options": {
                            "time_limit": 60,
                            "mip_gap": 0.02,
                        },
                        "model_options": {
                            "topology": "branched",  # "radial", "branched"
                            "feeder_route": "segmented",
                            "feeder_limit": "unlimited",
                        },
                    },
                    "offshore": False,
                    "floating": False,
                    "costs": {
                        "rated_power": 5000000.0,  # W
                        "num_blades": 3,
                        "rated_thrust_N": 823484.4216152605,  # from NREL 5MW definition
                        "gust_velocity_m_per_s": 70.0,  # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                        "blade_surface_area": 69.7974979,
                        "tower_mass": 620.4407337521,
                        "nacelle_mass": 101.98582836439,
                        "hub_mass": 8.38407517646,
                        "blade_mass": 14.56341339641,
                        "foundation_height": 0.0,
                        "commissioning_cost_kW": 44.0,  # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                        "decommissioning_cost_kW": 58.0,  # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                        "trench_len_to_substation_km": 50.0,
                        "distance_to_interconnect_mi": 4.97096954,
                        "interconnect_voltage_kV": 130.0,  # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                        "tcc_per_kW": 1300.00,  # (USD/kW)
                        "opex_per_kW": 44.00,  # (USD/kWh)
                    },
                },
                "analysis_options": {},
            },
        },
        "cost_parameters": {
            "cost_year": 2024,
        },
    }

    return ard_tech_dict


@fixture
def plant_config():
    site_config = {
        "latitude": 56.22732285,
        "longitude": 8.594398,
        "resources": {},
    }
    plant_dict = {
        "plant_life": 30,
        "simulation": {"n_timesteps": 8760, "dt": 3600, "start_time": "01/01 00:30:00"},
    }

    d = {"site": site_config, "plant": plant_dict}
    return d


def test_ard_wind_combined(plant_config, ard_config, subtests):
    os.chdir(EXAMPLE_DIR / "xx_wind_ard" / "ard_inputs")

    tech_config_dict = {
        "model_inputs": ard_config,
    }

    prob = om.Problem()

    wind_plant = ArdWindPlantModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    with subtests.test("AEP"):
        assert (
            pytest.approx(
                sum(prob.get_val("electricity_out", units="GW")),
                abs=1e-4,
            )
            == 150.8849096716472
        )

    with subtests.test("CapEx"):
        assert pytest.approx(np.sum(prob.get_val("CapEx", units="MUSD")), rel=1e-6) == 58.5

    with subtests.test("OpEx"):
        assert pytest.approx(np.sum(prob.get_val("OpEx", units="MUSD/year")), rel=1e-6) == 1.98
