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
                # "dt": 3600,
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

    ### MATH COULD DO THE JOB
    # integral from 0 to 24*365 of minimum(P_t, P_0 + A*sin(2*pi/24*t)) - P_t dt
    # integral from 0 to 24*365 of minimum(P_t, P_0 + A*sin(2*pi/24*t)) dt
    #       - 24*365*P_t  # rearranging
    # 365*(integral from 0 to 24 of minimum(P_t, P_0 + A*sin(2*pi/24*t)) dt
    #       - 24*P_t)  # moving constant
    # 365*(integral from -12 to 12 of minimum(P_t, P_0 + A*cos(2*pi/24*t)) dt
    #       - 24*P_t)  # by periodicity
    # # define x = t s.t. P_t == P_0 + A*cos(2*pi/24*t)
    # # => P_t - P_0 = A*cos(2*pi/24*x) => x = 24/(2*pi)*arccos((P_t - P_0)/A)
    # # +assuming P_t < P_0 + A
    # 365*(
    #     integral from -12 to -x of P_t dt
    #     + integral from -x to x of P_0 dt
    #     + integral from -x to x of A*cos(2*pi/24*t) dt
    #     + integral from x to 12 of P_t dt
    #     - 24*P_t
    # )  # split integral using regions of dominance
    # 365*(
    #     2*(P_0 - P_t)*x
    #     + integral from -x to x of A*cos(2*pi/24*t) dt
    # )  # simplify and reduce terms
    # # define w = 2*pi/24
    # # => x = 1/w*arccos((P_t - P_0)/A)
    # 365*(
    #     2*(P_0 - P_t)*x
    #     + 2*A/w*sin(w*x)
    # )  # simplify and reduce terms
    # 365*(
    #     2*(P_0 - P_t)*x
    #     + 2*A/w*sin(arccos((P_t - P_0)/A))
    # )  # simplify and reduce terms
    # 365*(
    #     2*(P_0 - P_t)*arccos((P_t - P_0)/A)
    #     + 24*A/pi*sqrt(1 - ((P_t - P_0)/A)**2)
    # )  # sin(arccos(f)) = sqrt(1 - f**2)
    ### GIVE UP HERE AND USE TRAPZ

    # verify deficit and surplus match expected values
    with subtests.test("net deficit match"):
        math_value = np.trapezoid(np.maximum(0.0, -(P_in - P_threshold)), h_in)
        assert np.isclose(
            prob.get_val("tspm.net_electricity_deficit", units="MW"),
            math_value,
            rtol=5.0e-4,
        )
    with subtests.test("net surplus match"):
        math_value = np.trapezoid(np.maximum(0.0, P_in - P_threshold), h_in)
        assert np.isclose(
            prob.get_val("tspm.net_electricity_surplus", units="MW"),
            math_value,
            rtol=1.0e-4,
        )

    # verify fraction of timesteps with deficit and surplus match expected values
    with subtests.test("fraction of timesteps with deficit match"):
        assert np.isclose(
            prob.get_val("tspm.frac_timestep_electricity_deficit"),
            0.6666666,
            rtol=1e-3,
        )
    with subtests.test("fraction of timesteps with surplus match"):
        assert np.isclose(
            prob.get_val("tspm.frac_timestep_electricity_surplus"),
            0.3333333,
            rtol=1e-3,
        )
    # (P - P_0)/A_sine
    # (P_threshold - P_0)/A_sine = (62.5 - 50.0)/25.0 = 0.5
    # arccos(0.5) -> 1.0471975512 => threshold exceeded 2.09439510239/(2*pi) = 33.333%
    # integral from -1.0471975512 to 1.0471975512 of cos(theta) = 1.7320508076


@pytest.mark.unit
@pytest.mark.parametrize(
    "demand_profile",
    [
        pytest.param(10.0, id="scalar_demand"),
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
        assert h2i.prob.get_val("threshold_stats.net_electricity_deficit", units="MW") == (
            pytest.approx(np.sum(np.maximum(0.0, expected_demand - electricity_in)))
        )

    with subtests.test("updating the demand input updates the threshold"):
        new_demand = np.full(n_timesteps, 3.0)
        h2i.prob.set_val("electrical_load_demand.electricity_demand", new_demand, units="MW")
        h2i.prob.run_model()
        assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
            pytest.approx(new_demand)
        )
        assert h2i.prob.get_val("threshold_stats.net_electricity_deficit", units="MW") == (
            pytest.approx(0.0)
        )
