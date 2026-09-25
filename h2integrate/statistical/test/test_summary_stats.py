import numpy as np
import pytest
import openmdao.api as om

from h2integrate.statistical import SummaryStatisticsPerformanceModel


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
                "percentiles": [5, 25, 50, 75, 95],
            },
        },
    }


@pytest.mark.unit
def test_summary_stats_sinusoid(plant_config, tech_config, subtests):
    prob = om.Problem()
    sspm = SummaryStatisticsPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config,
    )
    prob.model.add_subsystem("sspm", sspm, promotes=["*"])
    prob.setup()

    # set in the sinusoidal data
    h_in = np.arange(8760)
    A_sine = 25.0
    P_0 = 50.0
    T_sine = 24.0
    P_in = A_sine * np.sin(2 * np.pi / T_sine * h_in) + P_0
    prob.set_val("sspm.electricity_in", P_in, units="MW")
    prob.run_model()

    # verify percentiles were added correctly
    with subtests.test("config percentiles correct"):
        assert np.allclose(prob.model.sspm.config.percentiles, [5, 25, 50, 75, 95])

    # verify mean and standard deviation
    with subtests.test("mean match"):
        assert np.isclose(prob.get_val("sspm.electricity_mean", units="MW"), P_0)
    with subtests.test("stdev match"):
        assert np.isclose(prob.get_val("sspm.electricity_stdev", units="MW"), A_sine / np.sqrt(2))

    # verify median, min, and max
    with subtests.test("median match"):
        assert np.isclose(prob.get_val("sspm.electricity_median", units="MW"), P_0)
    with subtests.test("min match"):
        assert np.isclose(prob.get_val("sspm.electricity_min", units="MW"), P_0 - A_sine)
    with subtests.test("max match"):
        assert np.isclose(prob.get_val("sspm.electricity_max", units="MW"), P_0 + A_sine)

    # verify percentiles based on analytical math
    with subtests.test("percentiles match"):
        percentiles = prob.get_val("sspm.electricity_percentiles", units="MW")
        assert np.allclose(
            percentiles,
            [
                P_0 - A_sine * np.cos(2 * np.pi * 5 / 100 / 2),
                P_0 - A_sine * np.cos(2 * np.pi * 25 / 100 / 2),
                P_0,
                P_0 + A_sine * np.cos(2 * np.pi * 25 / 100 / 2),
                P_0 + A_sine * np.cos(2 * np.pi * 5 / 100 / 2),
            ],
            rtol=5e-2,
        )
        # note high tol required for discrete daily variation
