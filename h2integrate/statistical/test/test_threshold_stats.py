import numpy as np
import pytest
import openmdao.api as om

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
