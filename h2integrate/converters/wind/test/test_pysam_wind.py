import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
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

    prob.get_val("wind_plant.electricity_out")
    prob.get_val("wind_plant.annual_energy")
    prob.get_val("wind_plant.total_capacity")

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(prob.get_val("wind_plant.total_capacity", units="MW")[0], rel=1e-6)
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6)
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

    prob.get_val("wind_plant.electricity_out")
    prob.get_val("wind_plant.annual_energy")
    prob.get_val("wind_plant.total_capacity")

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(prob.get_val("wind_plant.total_capacity", units="MW")[0], rel=1e-6)
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6)
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

    prob.get_val("wind_plant.electricity_out")
    prob.get_val("wind_plant.annual_energy")
    prob.get_val("wind_plant.total_capacity")

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(prob.get_val("wind_plant.total_capacity", units="MW")[0], rel=1e-6)
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6)
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

    prob.get_val("wind_plant.electricity_out")
    prob.get_val("wind_plant.annual_energy")
    prob.get_val("wind_plant.total_capacity")

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(prob.get_val("wind_plant.total_capacity", units="MW")[0], rel=1e-6)
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6)
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

    prob.get_val("wind_plant.electricity_out")
    prob.get_val("wind_plant.annual_energy")
    prob.get_val("wind_plant.total_capacity")

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(prob.get_val("wind_plant.total_capacity", units="MW")[0], rel=1e-6)
            == expected_farm_capacity_MW
        )

    with subtests.test("wind AEP matches electricity out"):
        assert pytest.approx(
            prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6
        ) == np.sum(prob.get_val("wind_plant.electricity_out", units="MW"))

    with subtests.test("wind AEP value"):
        assert (
            pytest.approx(prob.get_val("wind_plant.annual_energy", units="MW*h/year")[0], rel=1e-6)
            == 2027210.444644157
        )


def test_pysam_wind_nonhourly_draft(subtests):
    import PySAM.Windpower as Windpower
    from PySAM.ResourceTools import SRW_to_wind_data

    # Run 60 min interval
    path = (
        EXAMPLE_DIR
        / "01_onshore_steel_mn"
        / "weather"
        / "wind"
        / "47.5_-93.0_windtoolkit_2013_60min_100m_120m.srw"
    )
    wind_data_60min = SRW_to_wind_data(path)

    system_mod_60min = Windpower.default("WindPowerSingleOwner")
    system_mod_60min.value("wind_resource_model_choice", 0)
    system_mod_60min.value("wind_resource_data", wind_data_60min)
    system_mod_60min.execute(0)

    wd_init = np.array(wind_data_60min["data"])
    for i in range(len(wd_init)):
        if i == 0:
            wind_data_15min = np.tile(wd_init[0], 4).reshape(4, 8)
        else:
            wind_data_15min = np.vstack([wind_data_15min, np.tile(wd_init[i], 4).reshape(4, 8)])

    wind_data_15min_dict = {
        "heights": wind_data_60min["heights"],
        "fields": wind_data_60min["fields"],
        "data": wind_data_15min.tolist(),
    }
    system_mod_15min = Windpower.default("WindPowerSingleOwner")
    system_mod_15min.value("wind_resource_model_choice", 0)
    system_mod_15min.value("wind_resource_data", wind_data_15min_dict)
    system_mod_15min.execute(0)

    with subtests.test("60 min: sum of generation == AEP"):
        assert (
            pytest.approx(np.sum(system_mod_60min.Outputs.gen), rel=1e-6)
            == system_mod_60min.Outputs.annual_energy
        )

    with subtests.test("15 min: sum of generation == AEP"):
        assert (
            pytest.approx(np.sum(system_mod_15min.Outputs.gen) * (15 / 60), rel=1e-6)
            == system_mod_15min.Outputs.annual_energy
        )

    with subtests.test("15 min AEP = 60 min AEP"):
        assert (
            pytest.approx(system_mod_15min.Outputs.annual_energy, rel=1e-6)
            == system_mod_60min.Outputs.annual_energy
        )

    # prob = om.Problem()

    # wind_plant = PYSAMWindPlantPerformanceModel(
    #     plant_config=plant_config,
    #     tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
    #     driver_config={},
    # )

    # plant_config['simulation']['dt'] = int(3600/4)
    # plant_config['simulation']['n_timesteps'] = int(8760*4)
