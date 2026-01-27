import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel
from h2integrate.resource.solar.nrel_developer_goes_api_models import GOESAggregatedSolarAPI


@fixture
def plant_config():
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }

    return {"plant": plant, "site": {"latitude": 30.6617, "longitude": -101.7096, "resources": {}}}


@fixture
def solar_resource_dict():
    pv_resource_dir = EXAMPLE_DIR / "11_hybrid_energy_plant" / "tech_inputs" / "weather" / "solar"
    pv_filename = "30.6617_-101.7096_psmv3_60_2013.csv"
    pv_resource_dict = {
        "resource_year": 2013,
        "resource_dir": pv_resource_dir,
        "resource_filename": pv_filename,
    }
    return pv_resource_dict


@fixture
def basic_pysam_options():
    pysam_options = {
        "SystemDesign": {
            "array_type": 2,
            "azimuth": 180,
            "bifaciality": 0.65,
            "inv_eff": 96.0,
            "losses": 14.0757,
            "module_type": 0,
            "rotlim": 45.0,
            "gcr": 0.3,
        },
    }
    return pysam_options


def test_pvwatts_outputs(basic_pysam_options, solar_resource_dict, plant_config, subtests):
    basic_pysam_options["SystemDesign"].update({"tilt": 0.0})
    pv_design_dict = {
        "pv_capacity_kWdc": 250000.0,
        "dc_ac_ratio": 1.23,
        "create_model_from": "default",
        "config_name": "PVWattsSingleOwner",
        "tilt": 0.0,
        "tilt_angle_func": "none",  # "lat-func",
        "pysam_options": basic_pysam_options,
    }

    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": pv_design_dict,
        }
    }

    prob = om.Problem()
    solar_resource = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=solar_resource_dict,
        driver_config={},
    )
    comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("solar_resource", solar_resource, promotes=["*"])
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    # Below are the base outputs that should be tested
    # base_outputs = ["capacity_factor", "replacement_schedule", "operational_life"]
    # base_outputs += [
    #     f"rated_{commodity}_production",
    #     f"annual_{commodity}_produced",
    #     f"total_{commodity}_produced",
    #     f"{commodity}_out",
    # ]

    # Check that replacement schedule is between 0 and 1
    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    # Check that capacity factor is between 0 and 1 with units of "unitless"
    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("capacity_factor", units="unitless") <= 1)

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


def test_pvwatts_singleowner_notilt(
    basic_pysam_options, solar_resource_dict, plant_config, subtests
):
    """Test `PYSAMSolarPlantPerformanceModel` with a basic input scenario:

    - `pysam_options` is provided
    - `create_model_from` is set to 'default'
    - `config_name` is 'PVWattsSingleOwner', this is used to create the starting system model
        because `create_model_from` is default.
    - `tilt_angle_func` is "none" and tilt is provided (in two separate places) as zero.
    """

    basic_pysam_options["SystemDesign"].update({"tilt": 0.0})
    pv_design_dict = {
        "pv_capacity_kWdc": 250000.0,
        "dc_ac_ratio": 1.23,
        "create_model_from": "default",
        "config_name": "PVWattsSingleOwner",
        "tilt": 0.0,
        "tilt_angle_func": "none",  # "lat-func",
        "pysam_options": basic_pysam_options,
    }

    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": pv_design_dict,
        }
    }

    prob = om.Problem()
    solar_resource = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=solar_resource_dict,
        driver_config={},
    )
    comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("solar_resource", solar_resource, promotes=["*"])
    prob.model.add_subsystem("pv_perf", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_electricity_produced")[0]
    system_capacity_AC = prob.get_val("pv_perf.system_capacity_AC")[0]
    system_capacity_DC = prob.get_val("pv_perf.system_capacity_DC")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 527345996

    with subtests.test("Capacity in kW-AC"):
        assert (
            pytest.approx(system_capacity_AC, rel=1e-6)
            == system_capacity_DC / pv_design_dict["dc_ac_ratio"]
        )

    with subtests.test("Capacity in kW-DC"):
        assert pytest.approx(system_capacity_DC, rel=1e-6) == pv_design_dict["pv_capacity_kWdc"]


def test_pvwatts_singleowner_notilt_different_site(basic_pysam_options, plant_config, subtests):
    """Test `PYSAMSolarPlantPerformanceModel` with a basic input scenario:

    - `pysam_options` is provided
    - `create_model_from` is set to 'default'
    - `config_name` is 'PVWattsSingleOwner', this is used to create the starting system model
        because `create_model_from` is default.
    - `tilt_angle_func` is "none" and tilt is provided (in two separate places) as zero.
    """

    driver_config = {
        "driver": {"design_of_experiments": {"flag": True}},
        "design_variables": {
            "site": {
                "latitude": {},
                "longitude": {},
            }
        },
    }
    plant_config["site"].update({"latitude": 35.2018863, "longitude": -101.945027})

    basic_pysam_options["SystemDesign"].update({"tilt": 0.0})
    pv_design_dict = {
        "pv_capacity_kWdc": 250000.0,
        "dc_ac_ratio": 1.23,
        "create_model_from": "default",
        "config_name": "PVWattsSingleOwner",
        "tilt": 0.0,
        "tilt_angle_func": "none",  # "lat-func",
        "pysam_options": basic_pysam_options,
    }

    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": pv_design_dict,
        }
    }

    solar_resource_dict = {
        "resource_year": 2012,
        "resource_dir": None,
        "resource_filename": "35.2018863_-101.945027_psmv3_60_2012.csv",
        "use_fixed_resource_location": False,
    }

    prob = om.Problem()
    solar_resource = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=solar_resource_dict,
        driver_config=driver_config,
    )
    comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("solar_resource", solar_resource, promotes=["*"])
    prob.model.add_subsystem("pv_perf", comp, promotes=["*"])
    prob.setup()

    prob.model.set_val("solar_resource.latitude", 34.22)
    prob.model.set_val("solar_resource.longitude", -102.75)
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_electricity_produced")[0]
    system_capacity_AC = prob.get_val("pv_perf.system_capacity_AC")[0]
    system_capacity_DC = prob.get_val("pv_perf.system_capacity_DC")[0]

    with subtests.test("Got updated site lat"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == 34.21

    with subtests.test("Got updated site lon"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == -102.74

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 553283237

    with subtests.test("Capacity in kW-AC"):
        assert (
            pytest.approx(system_capacity_AC, rel=1e-6)
            == system_capacity_DC / pv_design_dict["dc_ac_ratio"]
        )

    with subtests.test("Capacity in kW-DC"):
        assert pytest.approx(system_capacity_DC, rel=1e-6) == pv_design_dict["pv_capacity_kWdc"]


def test_pvwatts_singleowner_withtilt(
    basic_pysam_options, solar_resource_dict, plant_config, subtests
):
    """Test PYSAMSolarPlantPerformanceModel with tilt angle calculated using 'lat-func' option.
    The AEP of this test should be higher than the AEP in `test_pvwatts_singleowner_notilt`.
    """

    pv_design_dict = {
        "pv_capacity_kWdc": 250000.0,
        "dc_ac_ratio": 1.23,
        "create_model_from": "default",
        "config_name": "PVWattsSingleOwner",
        "tilt_angle_func": "lat-func",
        "pysam_options": basic_pysam_options,
    }

    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": pv_design_dict,
        }
    }

    prob = om.Problem()
    solar_resource = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=solar_resource_dict,
        driver_config={},
    )
    comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("solar_resource", solar_resource, promotes=["*"])
    prob.model.add_subsystem("pv_perf", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_electricity_produced")[0]
    system_capacity_AC = prob.get_val("pv_perf.system_capacity_AC")[0]
    system_capacity_DC = prob.get_val("pv_perf.system_capacity_DC")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 556443491

    with subtests.test("Capacity in kW-AC"):
        assert (
            pytest.approx(system_capacity_AC, rel=1e-6)
            == system_capacity_DC / pv_design_dict["dc_ac_ratio"]
        )

    with subtests.test("Capacity in kW-DC"):
        assert pytest.approx(system_capacity_DC, rel=1e-6) == pv_design_dict["pv_capacity_kWdc"]
