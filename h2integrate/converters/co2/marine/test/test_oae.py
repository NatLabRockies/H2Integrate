import unittest
import importlib

import numpy as np
import openmdao.api as om
from openmdao.utils.assert_utils import assert_near_equal


@unittest.skipUnless(importlib.util.find_spec("mcm") is not None, "mcm is not installed")
class TestOAEPerformanceModel(unittest.TestCase):
    def setUp(self):
        from h2integrate.converters.co2.marine.ocean_alkalinity_enhancement import (
            OAEPerformanceModel,
        )

        self.config = {
            "model_inputs": {
                "performance_parameters": {
                    "number_ed_min": 1,
                    "number_ed_max": 10,
                    "max_ed_system_flow_rate_m3s": 0.0324,  # m^3/s
                    "frac_base_flow": 0.5,
                    "assumed_CDR_rate": 0.8,  # mol CO2/mol NaOH
                    "use_storage_tanks": True,
                    "initial_tank_volume_m3": 0.0,  # m^3
                    "store_hours": 12.0,  # hours
                    "acid_disposal_method": "sell rca",
                    "initial_salinity_ppt": 73.76,  # ppt
                    "initial_temp_C": 10.0,  # degrees Celsius
                    "initial_dic_mol_per_L": 0.0044,  # mol/L
                    "initial_pH": 8.1,  # initial pH
                },
            },
        }

        driver_config = {
            "general": {
                "folder_output": "output",
            },
        }

        plant_config = {
            "plant": {
                "simulation": {
                    "n_timesteps": 8760,
                    "dt": 3600,
                }
            }
        }

        oae_model = OAEPerformanceModel(
            driver_config=driver_config, plant_config=plant_config, tech_config=self.config
        )
        self.prob = om.Problem(model=om.Group())
        self.prob.model.add_subsystem("OAE", oae_model, promotes=["*"])
        self.prob.setup()

    def test_performance_model(self):
        # Set inputs
        rng = np.random.default_rng(seed=42)
        base_power = np.linspace(3.0e8, 2.0e8, 8760)  # 300 MW to 200 MW over 8760 hours
        noise = rng.normal(loc=0, scale=0.5e8, size=8760)  # ±50 MW noise
        power_profile = base_power + noise
        self.prob.set_val("OAE.electricity_in", power_profile, units="W*h")

        # Run the model
        self.prob.run_model()

        # Get output values to determine expected values
        co2_out = self.prob.get_val("co2_out")
        co2_capture_mtpy = self.prob.get_val("co2_capture_mtpy")
        plant_mCC_capacity_mtph = self.prob.get_val("plant_mCC_capacity_mtph")
        alkaline_seawater_flow_rate = self.prob.get_val("alkaline_seawater_flow_rate")
        alkaline_seawater_pH = self.prob.get_val("alkaline_seawater_pH")
        excess_acid = self.prob.get_val("excess_acid")

        # Assert values (allowing for small numerical tolerance)
        assert_near_equal(np.mean(co2_out), 1108.394704250361, tolerance=1e-3)
        assert_near_equal(co2_capture_mtpy, [9709.53760923], tolerance=1e-6)
        assert_near_equal(plant_mCC_capacity_mtph, [1.10854656], tolerance=1e-6)
        assert_near_equal(np.mean(alkaline_seawater_flow_rate), 3.2395561643835618, tolerance=1e-6)
        assert_near_equal(np.mean(alkaline_seawater_pH), 9.145157555568293, tolerance=1e-6)
        assert_near_equal(np.mean(excess_acid), 58.32, tolerance=1e-6)


@unittest.skipUnless(importlib.util.find_spec("mcm") is None, "mcm is installed")
class TestOAEPerformanceModelNoMCM(unittest.TestCase):
    def test_no_mcm_import(self):
        from h2integrate.converters.co2.marine.ocean_alkalinity_enhancement import (
            OAEPerformanceModel,
        )

        try:
            self.model = OAEPerformanceModel(plant_config={}, tech_config={})
        except ImportError as e:
            self.assertIn(
                "The `mcm` package is required to use the Ocean Alkalinity Enhancement model."
                " Install it via:",
                str(e),
            )
        else:
            self.fail("ImportError was not raised")
