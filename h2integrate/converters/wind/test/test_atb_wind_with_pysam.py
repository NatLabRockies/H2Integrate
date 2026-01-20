import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel
from h2integrate.converters.wind.atb_wind_cost import ATBWindPlantCostModel
from h2integrate.resource.wind.nrel_developer_wtk_api import WTKNRELDeveloperAPIWindResource


@fixture
def wind_resource_config():
    wind_resource_dict = {
        "latitude": 35.2018863,
        "longitude": -101.945027,
        "resource_year": 2012,
    }
    return wind_resource_dict


@fixture
def plant_config():
    site_config = {
        "latitude": 35.2018863,
        "longitude": -101.945027,
    }
    plant_dict = {
        "plant_life": 30,
        "simulation": {"n_timesteps": 8760, "dt": 3600, "start_time": "01/01 00:30:00"},
    }

    d = {"site": site_config, "plant": plant_dict}
    return d


@fixture
def wind_plant_config():
    layout_config = {
        "layout_mode": "basicgrid",
        "layout_options": {
            "row_D_spacing": 5.0,
            "turbine_D_spacing": 5.0,
            "rotation_angle_deg": 0.0,
            "row_phase_offset": 0.0,
            "layout_shape": "square",
        },
    }
    pysam_config = {
        "Farm": {
            "wind_farm_wake_model": 0,
        },
        "Losses": {
            "ops_strategies_loss": 10.0,
        },
    }
    design_config = {
        "num_turbines": 50,
        "hub_height": 115,
        "rotor_diameter": 170,
        "turbine_rating_kw": 6000,
        "create_model_from": "default",
        "config_name": "WindPowerSingleOwner",
        "pysam_options": pysam_config,
        "layout": layout_config,
    }
    return design_config


def test_wind_plant_costs_with_pysam(
    wind_resource_config, plant_config, wind_plant_config, subtests
):
    cost_dict = {
        "capex_per_kW": 1000,  # overnight capital cost
        "opex_per_kW_per_year": 5,  # fixed operations and maintenance expenses
        "cost_year": 2022,
    }
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": wind_plant_config,
            "cost_parameters": cost_dict,
        }
    }

    prob = om.Problem()

    plant_config["site"].update({"resources": {"wind_resource": wind_resource_config}})

    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    wind_cost = ATBWindPlantCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.model.add_subsystem("wind_cost", wind_cost, promotes=["*"])
    prob.setup()
    prob.run_model()

    expected_farm_capacity_MW = (
        wind_plant_config["num_turbines"] * wind_plant_config["turbine_rating_kw"] / 1e3
    )

    capex = prob.get_val("wind_cost.CapEx")
    opex = prob.get_val("wind_cost.OpEx")

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW")[0], rel=1e-6
            )
            == expected_farm_capacity_MW
        )

    with subtests.test("wind farm capital cost"):
        assert (
            pytest.approx(capex[0], rel=1e-6)
            == expected_farm_capacity_MW * 1e3 * cost_dict["capex_per_kW"]
        )

    with subtests.test("wind farm operating cost"):
        assert (
            pytest.approx(opex[0], rel=1e-6)
            == expected_farm_capacity_MW * 1e3 * cost_dict["opex_per_kW_per_year"]
        )
