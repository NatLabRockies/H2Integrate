import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel
from h2integrate.converters.solar.atb_res_com_pv_cost import ATBResComPVCostModel
from h2integrate.converters.solar.atb_utility_pv_cost import ATBUtilityPVCostModel
from h2integrate.resource.solar.nrel_developer_goes_api_models import GOESAggregatedSolarAPI


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
def utility_scale_pv_performance_params():
    pysam_options = {
        "SystemDesign": {
            "array_type": 2,
            "bifaciality": 0.85,
            "inv_eff": 98.0,
            "losses": 10.0,
            "module_type": 1,
            "azimuth": 180,
            "rotlim": 45.0,
        },
        "SolarResource": {
            "albedo_default": 0.3,
        },
    }
    tech_params = {
        "pv_capacity_kWdc": 100 * 1e3,
        "dc_ac_ratio": 1.34,
        "create_model_from": "new",
        "tilt": 0,
        "tilt_angle_func": "none",
        # "config_name":
        "pysam_options": pysam_options,
    }
    return tech_params


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
def commercial_pv_performance_params():
    pysam_options = {
        "SystemDesign": {
            "array_type": 1,
            "module_type": 0,
        }
    }
    tech_params = {
        "pv_capacity_kWdc": 200,
        "dc_ac_ratio": 1.23,
        "create_model_from": "default",
        # "tilt": 0,
        "tilt_angle_func": "none",
        "config_name": "PVWattsCommercial",
        "pysam_options": pysam_options,
    }
    return tech_params


@fixture
def residential_pv_performance_params():
    pysam_options = {
        "SystemDesign": {
            "array_type": 1,
            "bifaciality": 0.0,
            "inv_eff": 96.0,
            "losses": 14.0,
            "module_type": 0,
            "azimuth": 180,
        }
    }
    tech_params = {
        "pv_capacity_kWdc": 7.9,
        "dc_ac_ratio": 1.21,
        "create_model_from": "default",
        "tilt": 20,
        "tilt_angle_func": "none",
        "config_name": "PVWattsResidential",
        "pysam_options": pysam_options,
    }
    return tech_params


def test_utility_pv_cost(
    utility_scale_pv_performance_params, solar_resource_dict, plant_config, subtests
):
    # costs from 2024_v3 ATB workbook using Solar - Utility PV costs
    # 2035 class 1 moderate
    cost_dict = {
        "capex_per_kWac": 764,  # overnight capital cost
        "opex_per_kWac_per_year": 15,  # fixed operations and maintenance expenses
        "cost_year": 2022,
    }
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": utility_scale_pv_performance_params,
            "cost_parameters": cost_dict,
        }
    }

    prob = om.Problem()
    solar_resource = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=solar_resource_dict,
        driver_config={},
    )
    perf_comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    cost_comp = ATBUtilityPVCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", solar_resource, promotes=["*"])
    prob.model.add_subsystem("pv_perf", perf_comp, promotes=["*"])
    prob.model.add_subsystem("pv_cost", cost_comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    pv_size_kWac = prob.get_val("pv_perf.system_capacity_AC")[0]
    capital_cost = prob.get_val("pv_cost.CapEx")[0]
    operating_cost = prob.get_val("pv_cost.OpEx")[0]

    with subtests.test("Utility PV AC Capacity"):
        assert pytest.approx(pv_size_kWac, rel=1e-6) == 74626.8
    with subtests.test("Utility PV Capital Cost"):
        assert pytest.approx(capital_cost, rel=1e-6) == pv_size_kWac * cost_dict["capex_per_kWac"]
    with subtests.test("Utility PV Operating Cost"):
        assert (
            pytest.approx(operating_cost, rel=1e-6)
            == pv_size_kWac * cost_dict["opex_per_kWac_per_year"]
        )


def test_commercial_pv_cost(
    commercial_pv_performance_params, solar_resource_dict, plant_config, subtests
):
    # costs from 2024_v3 ATB workbook using Solar - PV Dist. Comm costs
    # 2030 class 1 moderate
    cost_dict = {
        "capex_per_kWdc": 1439,  # overnight capital cost
        "opex_per_kWdc_per_year": 16,  # fixed operations and maintenance expenses
        "cost_year": 2022,
    }
    shared_value = commercial_pv_performance_params.pop("pv_capacity_kWdc")
    shared_params = {"pv_capacity_kWdc": shared_value}
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": shared_params,
            "performance_parameters": commercial_pv_performance_params,
            "cost_parameters": cost_dict,
        }
    }

    prob = om.Problem()
    solar_resource = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=solar_resource_dict,
        driver_config={},
    )

    perf_comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config, tech_config=tech_config_dict, driver_config={}
    )
    cost_comp = ATBResComPVCostModel(
        plant_config=plant_config, tech_config=tech_config_dict, driver_config={}
    )

    prob.model.add_subsystem("solar_resource", solar_resource, promotes=["*"])
    prob.model.add_subsystem("pv_perf", perf_comp, promotes=["*"])
    prob.model.add_subsystem("pv_cost", cost_comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    capital_cost = prob.get_val("pv_cost.CapEx")[0]
    operating_cost = prob.get_val("pv_cost.OpEx")[0]

    with subtests.test("Commercial Capital Cost"):
        assert pytest.approx(capital_cost, rel=1e-6) == shared_value * cost_dict["capex_per_kWdc"]
    with subtests.test("Commercial Operating Cost"):
        assert (
            pytest.approx(operating_cost, rel=1e-6)
            == shared_value * cost_dict["opex_per_kWdc_per_year"]
        )


def test_residential_pv_cost(
    residential_pv_performance_params, solar_resource_dict, plant_config, subtests
):
    # costs from 2024_v3 ATB workbook using Solar - PV Dist. Res costs
    # 2030 class 1 moderate
    cost_dict = {
        "capex_per_kWdc": 2111,  # overnight capital cost
        "opex_per_kWdc_per_year": 25,  # fixed operations and maintenance expenses
        "cost_year": 2022,
    }
    shared_value = residential_pv_performance_params.pop("pv_capacity_kWdc")
    shared_params = {"pv_capacity_kWdc": shared_value}
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": shared_params,
            "performance_parameters": residential_pv_performance_params,
            "cost_parameters": cost_dict,
        }
    }

    prob = om.Problem()
    solar_resource = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=solar_resource_dict,
        driver_config={},
    )
    perf_comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    cost_comp = ATBResComPVCostModel(
        plant_config=plant_config, tech_config=tech_config_dict, driver_config={}
    )
    prob.model.add_subsystem("solar_resource", solar_resource, promotes=["*"])
    prob.model.add_subsystem("pv_perf", perf_comp, promotes=["*"])
    prob.model.add_subsystem("pv_cost", cost_comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    capital_cost = prob.get_val("pv_cost.CapEx")[0]
    operating_cost = prob.get_val("pv_cost.OpEx")[0]

    with subtests.test("Residential Capital Cost"):
        assert pytest.approx(capital_cost, rel=1e-6) == shared_value * cost_dict["capex_per_kWdc"]
    with subtests.test("Residential Operating Cost"):
        assert (
            pytest.approx(operating_cost, rel=1e-6)
            == shared_value * cost_dict["opex_per_kWdc_per_year"]
        )
