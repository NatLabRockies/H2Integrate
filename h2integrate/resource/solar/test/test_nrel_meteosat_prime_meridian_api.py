from pathlib import Path

import openmdao.api as om
from pytest import fixture

from h2integrate.resource.solar.nrel_developer_meteosat_prime_meridian_models import (
    MeteosatPrimeMeridianSolarAPI,
    MeteosatPrimeMeridianTMYSolarAPI,
)


@fixture
def plant_simulation_config():
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }
    return plant


@fixture
def meteosat_prime_meridian_site():
    # Rome, Italy
    # filename: 41.9077_12.4368_2008_nsrdb_msg_v4_60min_utc_tz.csv
    meteosat_site = {
        "latitude": 41.9077,
        "longitude": 12.4368,
        "resources": {
            "solar_resource": {
                "resource_model": "meteosat_solar_v4_api",
                "resource_parameters": {
                    "resource_year": 2008,
                },
            }
        },
    }
    return meteosat_site


@fixture
def tmy_site():
    # Brisbane, Australia
    tmy_file = "-27.3649_152.67935_tmy-2020_himawari_tmy_v3_60min_utc_tz.csv"
    australia_site = {
        "latitude": -27.3649,
        "longitude": 152.67935,
        "resources": {
            "solar_resource": {
                "resource_model": "meteosat_tmy_solar_v4_api",
                "resource_parameters": {
                    "resource_year": "tmy-2022",
                    "resource_filename": tmy_file,
                },
            }
        },
    }
    return australia_site


def test_meteosat_prime_meridian(plant_simulation_config, meteosat_prime_meridian_site, subtests):
    plant_config = {
        "site": meteosat_prime_meridian_site,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    comp = MeteosatPrimeMeridianSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    data = prob.get_val("resource.solar_resource_data")

    name_expected = "41.9077_12.4368_2008_nsrdb_msg_v4_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name


def test_meteosat_prime_meridian_tmy(plant_simulation_config, tmy_site, subtests):
    plant_config = {
        "site": tmy_site,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    comp = MeteosatPrimeMeridianTMYSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    data = prob.get_val("resource.solar_resource_data")

    name_expected = "-27.3649_152.67935_tmy-2020_himawari_tmy_v3_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name
