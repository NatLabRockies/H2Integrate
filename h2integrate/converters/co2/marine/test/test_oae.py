import unittest
import importlib

import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture
from openmdao.utils.assert_utils import assert_near_equal


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }
    return plant_config


@fixture
def tech_config():
    return {
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


@fixture
def driver_config():
    driver_config = {
        "general": {
            "folder_output": "output",
        },
    }
    return driver_config


@pytest.mark.skipif(importlib.util.find_spec("mcm") is None, reason="mcm is not installed")
def test_doc_outputs(driver_config, plant_config, tech_config, subtests):
    from h2integrate.converters.co2.marine.ocean_alkalinity_enhancement import OAEPerformanceModel

    doc_model = OAEPerformanceModel(
        driver_config=driver_config, plant_config=plant_config, tech_config=tech_config
    )
    prob = om.Problem(model=om.Group())
    prob.model.add_subsystem("comp", doc_model, promotes=["*"])
    prob.setup()

    rng = np.random.default_rng(seed=42)
    base_power = np.linspace(3.0e8, 2.0e8, 8760)  # 300 MW to 200 MW over 8760 hours
    noise = rng.normal(loc=0, scale=0.5e8, size=8760)  # ±50 MW noise
    power_profile = base_power + noise
    prob.set_val("comp.electricity_in", power_profile, units="W")

    # Run the model
    prob.run_model()

    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    commodity = "co2"
    commodity_amount_units = "kg"
    commodity_rate_units = "kg/h"

    # Check that replacement schedule is between 0 and 1
    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    # Check that capacity factor is between 0 and 1 with units of "unitless"
    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") <= 1)

    # Check that capacity factor is between 1 and 100 with units of "percent"
    with subtests.test("1 <= capacity_factor (percent) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("comp.capacity_factor", units="unitless")) == plant_life

    # Test that rated commodity production is greater than zero
    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units) > 0
        )

    with subtests.test(f"rated_{commodity}_production length"):
        assert (
            len(prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units)) == 1
        )

    # Test that total commodity production is greater than zero
    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units) > 0
        )
    with subtests.test(f"total_{commodity}_produced length"):
        assert (
            len(prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units)) == 1
        )

    # Test that annual commodity production is greater than zero
    with subtests.test(f"annual_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr")
            > 0
        )

    with subtests.test(f"annual_{commodity}_produced[1:] == annual_{commodity}_produced[0]"):
        annual_production = prob.get_val(
            f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"annual_{commodity}_produced length"):
        assert len(annual_production) == plant_life

    # Test that commodity output has some values greater than zero
    with subtests.test(f"Some of {commodity}_out > 0"):
        assert np.any(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units) > 0)

    with subtests.test(f"{commodity}_out length"):
        assert len(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units)) == n_timesteps

    # Test default values
    with subtests.test("operational_life default value"):
        assert prob.get_val("comp.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


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
                "plant_life": 30,
                "simulation": {
                    "n_timesteps": 8760,
                    "dt": 3600,
                },
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
        self.prob.set_val("OAE.electricity_in", power_profile, units="W")

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
            plant_config = {
                "plant": {
                    "plant_life": 30,
                    "simulation": {
                        "n_timesteps": 8760,
                        "dt": 3600,
                    },
                }
            }
            self.model = OAEPerformanceModel(plant_config=plant_config, tech_config={})
        except ImportError as e:
            self.assertIn(
                "The `mcm` package is required to use the Ocean Alkalinity Enhancement model."
                " Install it via:",
                str(e),
            )
        else:
            self.fail("ImportError was not raised")
