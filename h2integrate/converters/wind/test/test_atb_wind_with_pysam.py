import pytest
import openmdao.api as om

from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel
from h2integrate.converters.wind.atb_wind_cost import ATBWindPlantCostModel
from h2integrate.resource.wind.nlr_developer_wtk_api import WTKNLRDeveloperAPIWindResource


@pytest.mark.regression
def test_wind_plant_costs_with_pysam(plant_config_wtk, wind_plant_config, subtests):
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

    wind_resource = WTKNLRDeveloperAPIWindResource(
        plant_config=plant_config_wtk,
        resource_config=plant_config_wtk["site"]["resource"]["wind_resource"][
            "resource_parameters"
        ],
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config_wtk,
        tech_config=tech_config_dict,
        driver_config={},
    )

    wind_cost = ATBWindPlantCostModel(
        plant_config=plant_config_wtk,
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

    capex = prob.get_val("wind_cost.CapEx", units="USD")
    opex = prob.get_val("wind_cost.OpEx", units="USD/year")

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
