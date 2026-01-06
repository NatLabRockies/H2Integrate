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

    aep = prob.get_val("pv_perf.annual_energy")[0]
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

    aep = prob.get_val("pv_perf.annual_energy")[0]
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

    aep = prob.get_val("pv_perf.annual_energy")[0]
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
