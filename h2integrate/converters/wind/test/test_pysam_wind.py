import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel
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


def test_pysam_wind_outputs(wind_resource_config, plant_config, wind_plant_config, subtests):
    prob = om.Problem()

    plant_config["site"].update({"resources": {"wind_resource": wind_resource_config}})

    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("comp", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

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


def test_wind_plant_pysam_no_changes_from_setup(
    wind_resource_config, plant_config, wind_plant_config, subtests
):
    prob = om.Problem()

    plant_config["site"].update({"resources": {"wind_resource": wind_resource_config}})

    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    expected_farm_capacity_MW = (
        wind_plant_config["num_turbines"] * wind_plant_config["turbine_rating_kw"] / 1e3
    )

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW")[0], rel=1e-6
            )
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0],
                rel=1e-6,
            )
            == 1014129.048439629
        )


def test_wind_plant_pysam_change_hub_height(
    wind_resource_config, plant_config, wind_plant_config, subtests
):
    prob = om.Problem()

    plant_config["site"].update({"resources": {"wind_resource": wind_resource_config}})

    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.set_val("wind_plant.hub_height", 130, units="m")
    prob.run_model()

    expected_farm_capacity_MW = (
        wind_plant_config["num_turbines"] * wind_plant_config["turbine_rating_kw"] / 1e3
    )

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW")[0], rel=1e-6
            )
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0],
                rel=1e-6,
            )
            == 1037360.7950548842
        )


def test_wind_plant_pysam_change_rotor_diameter(
    wind_resource_config, plant_config, wind_plant_config, subtests
):
    prob = om.Problem()

    plant_config["site"].update({"resources": {"wind_resource": wind_resource_config}})

    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.set_val("wind_plant.rotor_diameter", 155, units="m")
    prob.run_model()

    expected_farm_capacity_MW = (
        wind_plant_config["num_turbines"] * wind_plant_config["turbine_rating_kw"] / 1e3
    )

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW")[0], rel=1e-6
            )
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0],
                rel=1e-6,
            )
            == 916820.0472438652
        )


def test_wind_plant_pysam_change_turbine_rating(
    wind_resource_config, plant_config, wind_plant_config, subtests
):
    prob = om.Problem()

    plant_config["site"].update({"resources": {"wind_resource": wind_resource_config}})

    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    new_rating_MW = 5.5
    prob.set_val("wind_plant.wind_turbine_rating", new_rating_MW, units="MW")
    prob.run_model()

    expected_farm_capacity_MW = wind_plant_config["num_turbines"] * new_rating_MW

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW")[0], rel=1e-6
            )
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0],
                rel=1e-6,
            )
            == 968681.3512372728
        )


def test_wind_plant_pysam_change_n_turbines(
    wind_resource_config, plant_config, wind_plant_config, subtests
):
    prob = om.Problem()

    plant_config["site"].update({"resources": {"wind_resource": wind_resource_config}})

    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    new_num_turbines = 100
    prob.set_val("wind_plant.num_turbines", new_num_turbines)
    prob.run_model()

    expected_farm_capacity_MW = new_num_turbines * wind_plant_config["turbine_rating_kw"] / 1e3

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW")[0], rel=1e-6
            )
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/year")[0],
                rel=1e-6,
            )
            == 2027210.444644157
        )
