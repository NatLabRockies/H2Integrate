from pytest import fixture

from h2integrate.converters.solar.solar_baseclass import SolarPerformanceBaseClass


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


def test_solar_baseclass_initialization(plant_config, subtests):
    solar_base = SolarPerformanceBaseClass(
        plant_config=plant_config,
        tech_config={},
        driver_config={},
    )

    # At this point, the commodity attributes haven't been set

    solar_base.setup()

    with subtests.test("commodity"):
        assert solar_base.commodity == "electricity"
    with subtests.test("commodity_amount_units"):
        assert solar_base.commodity_amount_units == "kW*h"
    with subtests.test("commodity_rate_units"):
        assert solar_base.commodity_rate_units == "kW"
