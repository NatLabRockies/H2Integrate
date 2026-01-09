import numpy as np
import pytest
import CoolProp
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.wind.tools.resource_tools import (
    calculate_air_density,
    average_wind_data_for_hubheight,
    estimate_wind_speed_with_curve_fit,
    weighted_average_wind_data_for_hubheight,
)
from h2integrate.resource.wind.nrel_developer_wtk_api import WTKNRELDeveloperAPIWindResource


@fixture
def wind_resource_data():
    plant_config = {
        "site": {
            "latitude": 34.22,
            "longitude": -102.75,
            "resources": {
                "wind_resource": {
                    "resource_model": "wind_toolkit_v2_api",
                    "resource_parameters": {
                        "latitude": 35.2018863,
                        "longitude": -101.945027,
                        "resource_year": 2012,  # 2013,
                    },
                }
            },
        },
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 8760,
                "start_time": "01/01/1900 00:30:00",
                "timezone": 0,
            },
        },
    }

    prob = om.Problem()
    comp = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    wtk_data = prob.get_val("resource.wind_resource_data")

    return wtk_data


def test_air_density_calcs(subtests):
    z = 0
    T = 288.15 - 0.0065 * z
    P = 101325 * (1 - 2.25577e-5 * z) ** 5.25588
    rho0 = CoolProp.CoolProp.PropsSI("D", "T", T, "P", P, "Air")
    rho0_calc = calculate_air_density(z)
    with subtests.test("air density at sea level"):
        assert pytest.approx(rho0_calc, abs=1e-3) == rho0

    z = 500
    T = 288.15 - 0.0065 * z
    P = 101325 * (1 - 2.25577e-5 * z) ** 5.25588
    rho500m = CoolProp.CoolProp.PropsSI("D", "T", T, "P", P, "Air")
    rho500m_calc = calculate_air_density(z)
    with subtests.test("air density at 1000m"):
        assert pytest.approx(rho500m_calc, abs=1e-3) == rho500m


def test_resource_averaging(wind_resource_data, subtests):
    avg_windspeed = average_wind_data_for_hubheight(wind_resource_data, [100, 140], "wind_speed")
    i_lb_less_than_ub = np.argwhere(
        wind_resource_data["wind_speed_100m"] < wind_resource_data["wind_speed_140m"]
    ).flatten()
    with subtests.test("100m wind speed < average wind speed"):
        np.testing.assert_array_less(
            wind_resource_data["wind_speed_100m"][i_lb_less_than_ub],
            avg_windspeed[i_lb_less_than_ub],
        )

    with subtests.test("140m wind speed > average wind speed"):
        np.testing.assert_array_less(
            avg_windspeed[i_lb_less_than_ub],
            wind_resource_data["wind_speed_140m"][i_lb_less_than_ub],
        )

    with subtests.test("Wind speed at t=0 is average"):
        mean_ws = np.mean(
            [wind_resource_data["wind_speed_100m"][0], wind_resource_data["wind_speed_140m"][0]]
        )
        assert pytest.approx(avg_windspeed[0], rel=1e-6) == mean_ws

    with subtests.test("Avg Wind speed at t=0"):
        assert pytest.approx(avg_windspeed[0], rel=1e-6) == 15.78


def test_resource_equal_weighted_averaging(wind_resource_data, subtests):
    hub_height = 120
    avg_windspeed = weighted_average_wind_data_for_hubheight(
        wind_resource_data, [100, 140], hub_height, "wind_speed"
    )
    i_lb_less_than_ub = np.argwhere(
        wind_resource_data["wind_speed_100m"] < wind_resource_data["wind_speed_140m"]
    ).flatten()
    with subtests.test("100m wind speed < average wind speed"):
        np.testing.assert_array_less(
            wind_resource_data["wind_speed_100m"][i_lb_less_than_ub],
            avg_windspeed[i_lb_less_than_ub],
        )

    with subtests.test("140m wind speed > average wind speed"):
        np.testing.assert_array_less(
            avg_windspeed[i_lb_less_than_ub],
            wind_resource_data["wind_speed_140m"][i_lb_less_than_ub],
        )

    with subtests.test("Wind speed at t=0 is average"):
        mean_ws = np.mean(
            [wind_resource_data["wind_speed_100m"][0], wind_resource_data["wind_speed_140m"][0]]
        )
        assert pytest.approx(avg_windspeed[0], rel=1e-6) == mean_ws

    with subtests.test("Avg Wind speed at t=0"):
        assert pytest.approx(avg_windspeed[0], rel=1e-6) == 15.78


def test_resource_unequal_weighted_averaging(wind_resource_data, subtests):
    hub_height = 135
    weighted_avg_windspeed = weighted_average_wind_data_for_hubheight(
        wind_resource_data, [100, 140], hub_height, "wind_speed"
    )

    lb_to_avg_diff = np.abs(weighted_avg_windspeed - wind_resource_data["wind_speed_100m"])

    avg_to_ub_diff = np.abs(weighted_avg_windspeed - wind_resource_data["wind_speed_140m"])

    i_nonzero_diff = np.argwhere(
        (wind_resource_data["wind_speed_100m"] - wind_resource_data["wind_speed_140m"]) != 0
    ).flatten()

    # the weighted_avg_windspeed should be closer to the 140m height than the 100m
    with subtests.test("Weighted avg wind speed is closer to 140m wind speed than 100m wind speed"):
        np.testing.assert_array_less(avg_to_ub_diff[i_nonzero_diff], lb_to_avg_diff[i_nonzero_diff])

    with subtests.test("Weighted avg wind speed at t=0 is greater than equal average"):
        mean_ws = np.mean(
            [wind_resource_data["wind_speed_100m"][0], wind_resource_data["wind_speed_140m"][0]]
        )
        assert weighted_avg_windspeed[0] > mean_ws

    with subtests.test("Avg Wind speed at t=0"):
        assert pytest.approx(weighted_avg_windspeed[0], rel=1e-6) == 16.56


def test_wind_speed_curve_fit_estimate(wind_resource_data, subtests):
    hub_height = 120

    wind_speed_actual = wind_resource_data[f"wind_speed_{hub_height}m"]

    with subtests.test("Estimated wind speed is close to actual, single curve fit"):
        wind_speed_est = estimate_wind_speed_with_curve_fit(
            wind_resource_data, [100, 120], hub_height, run_per_timestep=False
        )
        np.testing.assert_array_almost_equal(wind_speed_est, wind_speed_actual)

    with subtests.test("Estimated wind speed is close to actual, multiple curve fit"):
        wind_speed_est = estimate_wind_speed_with_curve_fit(
            wind_resource_data, [100, 120], hub_height, run_per_timestep=True
        )
        np.testing.assert_array_almost_equal(wind_speed_est, wind_speed_actual)
