import shutil

import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import ROOT_DIR, H2I_LIBRARY_DIR
from h2integrate.core.utilities import load_yaml
from h2integrate.converters.wind.floris import FlorisWindPlantPerformanceModel
from h2integrate.resource.wind.openmeteo_wind import OpenMeteoHistoricalWindResource
from h2integrate.resource.wind.nrel_developer_wtk_api import WTKNRELDeveloperAPIWindResource


@fixture
def floris_config():
    floris_wake_config = load_yaml(H2I_LIBRARY_DIR / "floris_v4_default_template.yaml")
    floris_turbine_config = load_yaml(H2I_LIBRARY_DIR / "floris_turbine_Vestas_660kW.yaml")
    floris_performance_dict = {
        "num_turbines": 20,
        "floris_wake_config": floris_wake_config,
        "floris_turbine_config": floris_turbine_config,
        "default_turbulence_intensity": 0.06,
        "operation_model": "cosine-loss",
        "hub_height": -1,
        "layout": {
            "layout_mode": "basicgrid",
            "layout_options": {
                "row_D_spacing": 5.0,
                "turbine_D_spacing": 5.0,
            },
        },
        "operational_losses": 12.83,
        "enable_caching": False,
        "cache_dir": None,
        "resource_data_averaging_method": "nearest",
    }
    return floris_performance_dict


@fixture
def plant_config_openmeteo():
    site_config = {
        "latitude": 44.04218,
        "longitude": -95.19757,
        "resource": {
            "wind_resource": {
                "resource_model": "openmeteo_wind_api",
                "resource_parameters": {
                    "resource_year": 2023,
                },
            }
        },
    }
    plant_dict = {
        "plant_life": 30,
        "simulation": {"n_timesteps": 8760, "dt": 3600, "start_time": "01/01 00:30:00"},
    }

    d = {"site": site_config, "plant": plant_dict}
    return d


@fixture
def plant_config_wtk():
    site_config = {
        "latitude": 35.2018863,
        "longitude": -101.945027,
        "resource": {
            "wind_resource": {
                "resource_model": "wind_toolkit_v2_api",
                "resource_parameters": {
                    "resource_year": 2012,
                },
            }
        },
    }
    plant_dict = {
        "plant_life": 30,
        "simulation": {"n_timesteps": 8760, "dt": 3600, "start_time": "01/01 00:30:00"},
    }

    d = {"site": site_config, "plant": plant_dict}
    return d


def test_floris_outputs(plant_config_openmeteo, floris_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": floris_config,
        }
    }

    prob = om.Problem()

    wind_resource_config = plant_config_openmeteo["site"]["resource"]["wind_resource"][
        "resource_parameters"
    ]
    wind_resource = OpenMeteoHistoricalWindResource(
        plant_config=plant_config_openmeteo,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_openmeteo,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("comp", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"
    plant_life = int(plant_config_openmeteo["plant"]["plant_life"])
    n_timesteps = int(plant_config_openmeteo["plant"]["simulation"]["n_timesteps"])

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


def test_floris_wind_performance(plant_config_openmeteo, floris_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": floris_config,
        }
    }

    prob = om.Problem()

    wind_resource_config = plant_config_openmeteo["site"]["resource"]["wind_resource"][
        "resource_parameters"
    ]
    wind_resource = OpenMeteoHistoricalWindResource(
        plant_config=plant_config_openmeteo,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_openmeteo,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="kW")[0], rel=1e-6
            )
            == 660 * 20
        )

    with subtests.test("AEP"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="kW*h/year")[0],
                rel=1e-6,
            )
            == 36471.03023616864 * 1e3
        )

    with subtests.test("total electricity_out"):
        assert pytest.approx(
            np.sum(prob.get_val("wind_plant.electricity_out", units="kW")), rel=1e-6
        ) == prob.get_val("wind_plant.annual_electricity_produced", units="kW*h/year")


def test_floris_caching_changed_config(plant_config_openmeteo, floris_config, subtests):
    cache_dir = ROOT_DIR.parent / "test_cache_floris"

    # delete cache dir if it exists
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    floris_config["enable_caching"] = True
    floris_config["cache_dir"] = cache_dir

    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": floris_config,
        }
    }

    # Run FLORIS and get cache filename
    prob = om.Problem()

    wind_resource_config = plant_config_openmeteo["site"]["resource"]["wind_resource"][
        "resource_parameters"
    ]
    wind_resource = OpenMeteoHistoricalWindResource(
        plant_config=plant_config_openmeteo,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_openmeteo,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    cache_filename_init = list(cache_dir.glob("*.pkl"))

    with subtests.test("Check that cache file was created"):
        assert len(cache_filename_init) == 1

    # Modify something in the config and check that cache filename is different
    floris_config["operational_losses"] = 10.0
    prob = om.Problem()
    wind_resource = OpenMeteoHistoricalWindResource(
        plant_config=plant_config_openmeteo,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_openmeteo,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    cache_filenames = list(cache_dir.glob("*.pkl"))
    cache_filename_new = [file for file in cache_filenames if file not in cache_filename_init]

    with subtests.test("Check unique filename with modified config"):
        assert len(cache_filename_new) > 0

    with subtests.test("Check two cache files exist"):
        assert len(cache_filenames) == 2

    # Delete cache files and the testing cache dir
    shutil.rmtree(cache_dir)


def test_floris_caching_changed_inputs(plant_config_openmeteo, floris_config, subtests):
    cache_dir = ROOT_DIR.parent / "test_cache_floris"

    # delete cache dir if it exists
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    floris_config["enable_caching"] = True
    floris_config["cache_dir"] = cache_dir

    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": floris_config,
        }
    }

    # Run FLORIS and get cache filename
    prob = om.Problem()

    wind_resource_config = plant_config_openmeteo["site"]["resource"]["wind_resource"][
        "resource_parameters"
    ]
    wind_resource = OpenMeteoHistoricalWindResource(
        plant_config=plant_config_openmeteo,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_openmeteo,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    wind_resource_data = dict(prob.get_val("wind_resource.wind_resource_data"))

    cache_filename_init = list(cache_dir.glob("*.pkl"))

    with subtests.test("Check that cache file was created"):
        assert len(cache_filename_init) == 1

    # Modify the wind resource data, rerun floris, and check that a new file was created
    # wind_resource_data['wind_speed_100m'][10] += 1 #this wont trigger a new cache file
    wind_resource_data["site_lat"] = 44.04218107666016

    prob = om.Problem()

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_openmeteo,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_plant", wind_plant)
    prob.setup()
    prob.set_val("wind_plant.wind_resource_data", wind_resource_data)
    prob.run_model()

    cache_filenames = list(cache_dir.glob("*.pkl"))
    cache_filename_new = [file for file in cache_filenames if file not in cache_filename_init]

    with subtests.test("Check unique filename with modified config"):
        assert len(cache_filename_new) > 0

    with subtests.test("Check two cache files exist"):
        assert len(cache_filenames) == 2

    # Delete cache files and the testing cache dir
    shutil.rmtree(cache_dir)


def test_floris_wind_performance_air_dens(plant_config_wtk, floris_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": floris_config,
        }
    }

    prob = om.Problem()

    wind_resource_config = plant_config_wtk["site"]["resource"]["wind_resource"][
        "resource_parameters"
    ]
    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config_wtk,
        resource_config=wind_resource_config,
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_wtk,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    wind_resource_data = dict(prob.get_val("wind_resource.wind_resource_data"))

    initial_aep = prob.get_val("wind_plant.annual_electricity_produced", units="kW*h/year")[0]
    with subtests.test("wind farm capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="kW")[0], rel=1e-6
            )
            == 660 * 20
        )

    with subtests.test("AEP"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="kW*h/year")[0],
                rel=1e-6,
            )
            == 37007.33639643173 * 1e3
        )

    with subtests.test("total electricity_out"):
        assert pytest.approx(
            np.sum(prob.get_val("wind_plant.electricity_out", units="kW")), rel=1e-6
        ) == prob.get_val("wind_plant.annual_electricity_produced", units="kW*h/year")

    # Add elevation to the resource data and rerun floris
    floris_config["adjust_air_density_for_elevation"] = True
    wind_resource_data["elevation"] = 1133.0

    prob = om.Problem()

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config_wtk,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("wind_plant", wind_plant)
    prob.setup()
    prob.set_val("wind_plant.wind_resource_data", wind_resource_data)
    prob.run_model()

    adjusted_aep = prob.get_val("wind_plant.annual_electricity_produced", units="kW*h/year")[0]
    with subtests.test("reduced AEP with air density adjustment"):
        assert adjusted_aep < initial_aep

    with subtests.test("AEP with air density adjustment"):
        assert pytest.approx(adjusted_aep, rel=1e-6) == 34392.58173437373 * 1e3
