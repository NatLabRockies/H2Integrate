import numpy as np
import pytest
import openmdao.api as om

from h2integrate import H2IntegrateModel
from h2integrate.statistical import ThresholdStatisticsPerformanceModel


@pytest.fixture
def plant_config():
    return {
        "plant": {
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }


@pytest.fixture
def tech_config():
    return {
        "model_inputs": {
            "performance_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "MW",
                "commodity_amount_units": "MW*h",
                # "epsilon_comparison": 1.0e-3,
            },
        },
    }


@pytest.mark.unit
def test_threshold_stats_sinusoid(plant_config, tech_config, subtests):
    prob = om.Problem()
    tspm = ThresholdStatisticsPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config,
    )
    prob.model.add_subsystem("tspm", tspm, promotes=["*"])
    prob.setup()

    # set in the sinusoidal data
    h_in = np.arange(8760)
    A_sine = 25.0
    P_0 = 50.0
    T_sine = 24.0
    P_in = A_sine * np.sin(2 * np.pi / T_sine * h_in) + P_0
    prob.set_val("tspm.electricity_in", P_in, units="MW")

    # set in a constant threshold
    P_threshold = 62.5
    prob.set_val("tspm.electricity_threshold", P_threshold, units="MW")

    prob.run_model()

    # verify deficit and surplus match expected values
    with subtests.test("net deficit match"):
        math_value = np.trapezoid(np.maximum(0.0, -(P_in - P_threshold)), h_in)
        assert np.isclose(
            prob.get_val("tspm.net_electricity_deficit", units="MW*h"),
            math_value,
            rtol=5.0e-4,
        )
    with subtests.test("net surplus match"):
        math_value = np.trapezoid(np.maximum(0.0, P_in - P_threshold), h_in)
        assert np.isclose(
            prob.get_val("tspm.net_electricity_surplus", units="MW*h"),
            math_value,
            rtol=1.0e-4,
        )

    # verify fraction of timesteps with deficit and surplus match expected values
    with subtests.test("fraction of timesteps with deficit match"):
        assert np.isclose(
            prob.get_val("tspm.ratio_timestep_electricity_deficit"),
            0.6666666,
            rtol=1e-3,
        )
    with subtests.test("fraction of timesteps with surplus match"):
        assert np.isclose(
            prob.get_val("tspm.ratio_timestep_electricity_surplus"),
            0.3333333,
            rtol=1e-3,
        )
    # (P - P_0)/A_sine
    # (P_threshold - P_0)/A_sine = (62.5 - 50.0)/25.0 = 0.5
    # arccos(0.5) -> 1.0471975512 => threshold exceeded 2.09439510239/(2*pi) = 33.333%
    # integral from -1.0471975512 to 1.0471975512 of cos(theta) = 1.7320508076


@pytest.mark.unit
@pytest.mark.parametrize(
    "commodity, rate_units, amount_units, dt, expected_deficit, expected_surplus",
    [
        pytest.param("hydrogen", "kg/h", "kg", 3600, 7.0, 5.0, id="mass_per_hour"),
        pytest.param("electricity", "kW", "kW*min", 900, 105.0, 75.0, id="quarter_hour_minutes"),
    ],
)
def test_threshold_stats_amount_units(
    plant_config,
    tech_config,
    commodity,
    rate_units,
    amount_units,
    dt,
    expected_deficit,
    expected_surplus,
):
    plant_config["plant"]["simulation"].update(n_timesteps=4, dt=dt)
    tech_config["model_inputs"]["performance_parameters"].update(
        commodity=commodity, commodity_rate_units=rate_units, commodity_amount_units=amount_units
    )
    prob = om.Problem()
    prob.model.add_subsystem(
        "tspm",
        ThresholdStatisticsPerformanceModel(plant_config=plant_config, tech_config=tech_config),
    )
    prob.setup()
    prob.set_val(f"tspm.{commodity}_in", [2.0, 8.0, 7.0, 1.0], units=rate_units)
    prob.set_val(f"tspm.{commodity}_threshold", [5.0, 5.0, 5.0, 5.0], units=rate_units)
    prob.run_model()

    assert prob.get_val(f"tspm.net_{commodity}_deficit", units=amount_units) == pytest.approx(
        expected_deficit
    )
    assert prob.get_val(f"tspm.net_{commodity}_surplus", units=amount_units) == pytest.approx(
        expected_surplus
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "demand_profile",
    [
        pytest.param(10.0 * np.ones(8760), id="scalar_demand"),
        pytest.param((np.arange(8760) % 24 + 1.0).tolist(), id="demand_array"),
    ],
)
def test_threshold_from_demand_component(demand_profile, subtests):
    """The threshold is shared with a demand component through an input-to-input connection."""
    n_timesteps = 8760
    h2i_config = {
        "name": "H2I",
        "system_summary": "",
        "driver_config": {"name": "driver_config", "description": "", "general": {}},
        "technology_config": {
            "name": "technology_config",
            "description": "",
            "technologies": {
                "electrical_load_demand": {
                    "performance_model": {"model": "GenericDemandComponent"},
                    "model_inputs": {
                        "performance_parameters": {
                            "commodity": "electricity",
                            "commodity_rate_units": "MW",
                            "demand_profile": demand_profile,
                        },
                    },
                },
                "threshold_stats": {
                    "performance_model": {"model": "ThresholdStatisticsPerformanceModel"},
                    "model_inputs": {
                        "performance_parameters": {
                            "commodity": "electricity",
                            "commodity_rate_units": "MW",
                            "commodity_amount_units": "MW*h",
                        },
                    },
                },
            },
        },
        "plant_config": {
            "name": "plant_config",
            "description": "",
            "plant": {"plant_life": 30, "simulation": {"n_timesteps": n_timesteps, "dt": 3600}},
            "technology_interconnections": [
                [
                    "electrical_load_demand",
                    "threshold_stats",
                    ["electricity_demand", "electricity_threshold"],
                ],
            ],
        },
    }

    h2i = H2IntegrateModel(h2i_config)
    h2i.model.connect(
        "electrical_load_demand.electricity_demand", "threshold_stats.electricity_threshold"
    )  # DEBUG!!!!! HOTFIX!!!!!
    h2i.model.set_input_defaults(
        "electrical_load_demand.electricity_demand",
        demand_profile,
        units="MW",
    )  # DEBUG!!!!! HOTFIX!!!!!
    h2i.setup()

    expected_demand = np.broadcast_to(np.asarray(demand_profile, dtype=float), n_timesteps)
    electricity_in = np.full(n_timesteps, 6.0)
    h2i.prob.set_val("threshold_stats.electricity_in", electricity_in, units="MW")
    h2i.run()

    with subtests.test("threshold defaults to the demand profile"):
        assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
            pytest.approx(expected_demand)
        )

    with subtests.test("statistics use the demand profile as the threshold"):
        assert h2i.prob.get_val("threshold_stats.net_electricity_deficit", units="MW*h") == (
            pytest.approx(np.sum(np.maximum(0.0, expected_demand - electricity_in)))
        )

    with subtests.test("updating the demand input updates the threshold"):
        new_demand = np.full(n_timesteps, 3.0)
        h2i.prob.set_val("electrical_load_demand.electricity_demand", new_demand, units="MW")
        h2i.prob.run_model()
        assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
            pytest.approx(new_demand)
        )
        assert h2i.prob.get_val("threshold_stats.net_electricity_deficit", units="MW*h") == (
            pytest.approx(0.0)
        )
