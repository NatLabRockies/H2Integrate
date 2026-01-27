import unittest
import importlib

import numpy as np
import openmdao.api as om
from openmdao.utils.assert_utils import assert_near_equal


@unittest.skipUnless(importlib.util.find_spec("mcm") is not None, "mcm is not installed")
class TestDOCPerformanceModel(unittest.TestCase):
    def setUp(self):
        from h2integrate.converters.co2.marine.direct_ocean_capture import DOCPerformanceModel

        self.config = {
            "model_inputs": {
                "performance_parameters": {
                    "power_single_ed_w": 24000000.0,  # W
                    "flow_rate_single_ed_m3s": 0.6,  # m^3/s
                    "number_ed_min": 1,
                    "number_ed_max": 10,
                    "E_HCl": 0.05,  # kWh/mol
                    "E_NaOH": 0.05,  # kWh/mol
                    "y_ext": 0.9,
                    "y_pur": 0.2,
                    "y_vac": 0.6,
                    "frac_ed_flow": 0.01,
                    "use_storage_tanks": True,
                    "initial_tank_volume_m3": 0.0,  # m^3
                    "store_hours": 12.0,  # hours
                    "sal": 33.0,  # ppt
                    "temp_C": 12.0,  # degrees Celsius
                    "dic_i": 0.0022,  # mol/L
                    "pH_i": 8.1,  # initial pH
                },
            },
        }
        plant_config = {
            "plant": {
                "plant_life": 30,
                "simulation": {
                    "n_timesteps": 8760,  # Default number of timesteps for the simulation
                    "dt": 3600,
                },
            },
        }

        driver_config = {
            "general": {
                "folder_output": "output",
            },
        }

        doc_model = DOCPerformanceModel(
            driver_config=driver_config, plant_config=plant_config, tech_config=self.config
        )
        self.prob = om.Problem(model=om.Group())
        self.prob.model.add_subsystem("DOC", doc_model, promotes=["*"])
        self.prob.setup()

    def test_performance_model(self):
        # Set inputs
        rng = np.random.default_rng(seed=42)
        base_power = np.linspace(3.0e8, 2.0e8, 8760)  # 5 MW to 10 MW over 8760 hours
        noise = rng.normal(loc=0, scale=0.5e8, size=8760)  # ±0.5 MW noise
        power_profile = base_power + noise
        self.prob.set_val("DOC.electricity_in", power_profile, units="W")

        # Run the model
        self.prob.run_model()

        # Additional asserts for output values
        co2_out = self.prob.get_val("co2_out")
        co2_capture_mtpy = self.prob.get_val("co2_capture_mtpy")
        plant_mCC_capacity_mtph = self.prob.get_val("plant_mCC_capacity_mtph")
        total_tank_volume_m3 = self.prob.get_val("total_tank_volume_m3")

        # Assert values (allowing for small numerical tolerance)
        assert_near_equal(np.linalg.norm(co2_out), 11394970.06218, tolerance=1e-1)
        assert_near_equal(np.linalg.norm(co2_capture_mtpy), [1041164.44000004], tolerance=1e-5)
        assert_near_equal(plant_mCC_capacity_mtph, [176.34], tolerance=1e-2)
        assert_near_equal(total_tank_volume_m3, [25920.0], tolerance=1e-2)


@unittest.skipUnless(importlib.util.find_spec("mcm") is None, "mcm is installed")
class TestDOCPerformanceModelNoMCM(unittest.TestCase):
    def test_no_mcm_import(self):
        from h2integrate.converters.co2.marine.direct_ocean_capture import DOCPerformanceModel

        try:
            plant_config = {
                "plant": {
                    "plant_life": 30,
                    "simulation": {
                        "n_timesteps": 8760,  # Default number of timesteps for the simulation
                        "dt": 3600,
                    },
                },
            }
            self.model = DOCPerformanceModel(plant_config=plant_config, tech_config={})
        except ImportError as e:
            self.assertIn(
                "The `mcm` package is required to use the Direct Ocean Capture model."
                " Install it via:",
                str(e),
            )
        else:
            self.fail("ImportError was not raised")
