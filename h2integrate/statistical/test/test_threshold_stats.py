from unittest.mock import patch

import yaml
import numpy as np
import pytest
import openmdao.api as om
from openmdao.utils.om_warnings import UnitsWarning, PromotionWarning

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


@pytest.fixture
def demand_threshold_config():
    n_timesteps = 8760
    return {
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
                            "demand_profile": 10.0,
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
                "second_threshold_stats": {
                    "performance_model": {"model": "ThresholdStatisticsPerformanceModel"},
                    "model_inputs": {
                        "performance_parameters": {
                            "commodity": "electricity",
                            "commodity_rate_units": "kW",
                            "commodity_amount_units": "kW*h",
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
                [
                    "electrical_load_demand",
                    "second_threshold_stats",
                    ["electricity_demand", "electricity_threshold"],
                ],
            ],
        },
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "demand_profile",
    [
        pytest.param(10.0, id="scalar"),
        pytest.param(10, id="integer_scalar"),
        pytest.param(10.0 * np.ones(8760), id="array"),
        pytest.param((np.arange(8760) % 24 + 1.0).tolist(), id="list"),
    ],
)
@pytest.mark.parametrize("demand_model", ["GenericDemandComponent", "FlexibleDemandComponent"])
def test_threshold_from_demand_component(
    demand_threshold_config, demand_profile, demand_model, subtests
):
    """Demand inputs share their configured default and runtime updates with thresholds."""
    n_timesteps = 8760
    demand = demand_threshold_config["technology_config"]["technologies"]["electrical_load_demand"]
    demand["performance_model"]["model"] = demand_model
    parameters = demand["model_inputs"].pop("performance_parameters")
    parameters["demand_profile"] = demand_profile
    demand["model_inputs"]["shared_parameters"] = parameters
    demand["model_inputs"]["performance_parameters"] = {}
    if demand_model == "FlexibleDemandComponent":
        demand["model_inputs"]["performance_parameters"].update(
            rated_demand=30.0,
            turndown_ratio=0.1,
            ramp_down_rate_fraction=1.0,
            ramp_up_rate_fraction=1.0,
            min_utilization=0.0,
        )

    h2i = H2IntegrateModel(demand_threshold_config)
    h2i.setup()

    expected_demand = np.broadcast_to(np.asarray(demand_profile, dtype=float), n_timesteps)
    electricity_in = np.full(n_timesteps, 6.0)
    h2i.prob.set_val("threshold_stats.electricity_in", electricity_in, units="MW")
    h2i.run()

    with subtests.test("threshold defaults to the demand profile"):
        assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
            pytest.approx(expected_demand)
        )
        assert h2i.prob.get_val("second_threshold_stats.electricity_threshold", units="kW") == (
            pytest.approx(expected_demand * 1000)
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
        assert h2i.prob.get_val("second_threshold_stats.electricity_threshold", units="kW") == (
            pytest.approx(new_demand * 1000)
        )
        assert h2i.prob.get_val("threshold_stats.net_electricity_deficit", units="MW*h") == (
            pytest.approx(0.0)
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "tech_name,parameter,expected",
    [
        ("electrical_load_demand", "electricity_demand", True),
        ("electrical_load_demand", "electricity_in", False),
        ("electrical_load_demand", "unmet_electricity_demand_out", False),
        ("threshold_stats", "electricity_threshold", False),
        ("missing_technology", "electricity_demand", False),
    ],
)
def test_is_demand_input_profile(demand_threshold_config, tech_name, parameter, expected):
    """Only demand-profile inputs receive automatic shared defaults."""
    h2i = H2IntegrateModel(demand_threshold_config)
    assert h2i._is_demand_input_profile(tech_name, parameter) is expected


@pytest.mark.unit
def test_demand_default_is_registered_once_on_source(demand_threshold_config):
    """One source default initializes multiple destinations with different input defaults."""
    with patch.object(
        om.Group, "set_input_defaults", autospec=True, side_effect=om.Group.set_input_defaults
    ) as set_defaults:
        h2i = H2IntegrateModel(demand_threshold_config)

    top_level_calls = [call for call in set_defaults.call_args_list if call.args[0] is h2i.model]
    assert len(top_level_calls) == 1
    assert top_level_calls[0].args[1] == "electrical_load_demand.electricity_demand"
    assert top_level_calls[0].kwargs["val"] == pytest.approx(np.full(8760, 10.0))
    assert top_level_calls[0].kwargs["units"] == "MW"

    h2i.run()
    assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
        pytest.approx(np.full(8760, 10.0))
    )
    assert h2i.prob.get_val("second_threshold_stats.electricity_threshold", units="kW") == (
        pytest.approx(np.full(8760, 10000.0))
    )


@pytest.mark.unit
@pytest.mark.parametrize("update_before_first_run", [True, False])
def test_shared_demand_can_be_updated_through_destination(
    demand_threshold_config, update_before_first_run, subtests
):
    """A destination assignment updates the shared source, not an independent threshold."""
    h2i = H2IntegrateModel(demand_threshold_config)
    h2i.setup()
    if not update_before_first_run:
        h2i.run()

    h2i.prob.set_val(
        "second_threshold_stats.electricity_threshold", np.full(8760, 8000.0), units="kW"
    )
    h2i.run()

    with subtests.test("all inputs share the same Auto-IVC output"):
        demand_source = h2i.model.get_source("electrical_load_demand.electricity_demand")
        assert demand_source.startswith("_auto_ivc.")
        assert h2i.model.get_source("threshold_stats.electricity_threshold") == demand_source
        assert h2i.model.get_source("second_threshold_stats.electricity_threshold") == demand_source

    with subtests.test("destination updates reach demand and both thresholds"):
        for variable in (
            "electrical_load_demand.electricity_demand",
            "threshold_stats.electricity_threshold",
            "second_threshold_stats.electricity_threshold",
        ):
            assert h2i.prob.get_val(variable, units="MW") == pytest.approx(np.full(8760, 8.0))


@pytest.mark.unit
def test_threshold_from_connected_demand_input(demand_threshold_config, subtests):
    """An output driving demand takes precedence over the configured default."""
    technologies = demand_threshold_config["technology_config"]["technologies"]
    technologies["upstream_demand"] = {
        "performance_model": {"model": "GenericDemandComponent"},
        "model_inputs": {
            "performance_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "MW",
                "demand_profile": [4.0] + [12.0] * 8759,
            },
        },
    }
    demand_threshold_config["plant_config"]["technology_interconnections"].insert(
        0,
        [
            "upstream_demand",
            "electrical_load_demand",
            ["unmet_electricity_demand_out[0]", "electricity_demand[0:8760]"],
        ],
    )

    h2i = H2IntegrateModel(demand_threshold_config)
    h2i.run()

    with subtests.test("the upstream output drives the demand and both thresholds"):
        for variable in (
            "electrical_load_demand.electricity_demand",
            "threshold_stats.electricity_threshold",
            "second_threshold_stats.electricity_threshold",
        ):
            assert h2i.prob.get_val(variable, units="MW") == pytest.approx(np.full(8760, 4.0))


@pytest.mark.unit
def test_non_demand_input_connection_requires_shared_defaults(demand_threshold_config, subtests):
    """Other input-to-input connections use explicitly configured OpenMDAO defaults."""
    connections = demand_threshold_config["plant_config"]["technology_interconnections"]
    connections[1] = [
        "threshold_stats",
        "second_threshold_stats",
        ["electricity_in", "electricity_threshold"],
    ]

    h2i = H2IntegrateModel(demand_threshold_config)
    with subtests.test("different units require an explicit shared default"):
        with pytest.warns(UnitsWarning), pytest.raises(RuntimeError, match="different units"):
            h2i.run()

    h2i = H2IntegrateModel(demand_threshold_config)
    h2i.model.set_input_defaults(
        "threshold_stats.electricity_in", val=np.full(8760, 7.0), units="MW"
    )
    h2i.run()
    with subtests.test("the explicit default is shared"):
        assert h2i.prob.get_val("second_threshold_stats.electricity_threshold", units="MW") == (
            pytest.approx(np.full(8760, 7.0))
        )

    h2i.prob.set_val("threshold_stats.electricity_in", 4.0, units="MW")
    h2i.prob.run_model()
    with subtests.test("runtime updates are shared"):
        assert h2i.prob.get_val("second_threshold_stats.electricity_threshold", units="MW") == (
            pytest.approx(np.full(8760, 4.0))
        )


@pytest.mark.unit
def test_shared_demand_default_can_be_overridden(demand_threshold_config):
    """Users can override the default before setup without changing the configured profile."""
    h2i = H2IntegrateModel(demand_threshold_config)
    with pytest.warns(PromotionWarning, match="override previously set defaults"):
        h2i.model.set_input_defaults(
            "electrical_load_demand.electricity_demand", val=np.full(8760, 8.0), units="MW"
        )
    h2i.run()
    assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
        pytest.approx(np.full(8760, 8.0))
    )


@pytest.mark.unit
def test_hydrogen_demand_shared_default(demand_threshold_config):
    """The demand default works for commodities other than electricity."""
    technologies = demand_threshold_config["technology_config"]["technologies"]
    for tech in technologies.values():
        params = tech["model_inputs"]["performance_parameters"]
        params["commodity"] = "hydrogen"
        params["commodity_rate_units"] = "(kg/h)"
        if "commodity_amount_units" in params:
            params["commodity_amount_units"] = "kg"
    for connection in demand_threshold_config["plant_config"]["technology_interconnections"]:
        connection[2] = ["hydrogen_demand", "hydrogen_threshold"]

    h2i = H2IntegrateModel(demand_threshold_config)
    h2i.run()
    assert h2i.prob.get_val("threshold_stats.hydrogen_threshold", units="kg/h") == (
        pytest.approx(np.full(8760, 10.0))
    )


@pytest.mark.unit
def test_sliced_demand_input_connection(demand_threshold_config):
    """Source indices select the configured demand profile for a connected input."""
    demand = demand_threshold_config["technology_config"]["technologies"]["electrical_load_demand"]
    demand["model_inputs"]["performance_parameters"]["demand_profile"] = list(range(1, 8761))
    demand_threshold_config["plant_config"]["technology_interconnections"][0][2] = [
        "electricity_demand[0]",
        "electricity_threshold[0:8760]",
    ]

    h2i = H2IntegrateModel(demand_threshold_config)
    h2i.run()
    assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
        pytest.approx(np.ones(8760))
    )
    assert h2i.prob.get_val("second_threshold_stats.electricity_threshold", units="MW") == (
        pytest.approx(np.arange(1, 8761))
    )


@pytest.mark.unit
@pytest.mark.parametrize("reverse_connections", [False, True])
def test_chained_demand_inputs(demand_threshold_config, reverse_connections):
    """The upstream demand owns the shared default regardless of connection order."""
    technologies = demand_threshold_config["technology_config"]["technologies"]
    technologies["intermediate_demand"] = {
        "performance_model": {"model": "GenericDemandComponent"},
        "model_inputs": {
            "performance_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "MW",
                "demand_profile": 20.0,
            },
        },
    }
    connections = [
        [
            "electrical_load_demand",
            "intermediate_demand",
            ["electricity_demand", "electricity_demand"],
        ],
        ["intermediate_demand", "threshold_stats", ["electricity_demand", "electricity_threshold"]],
        [
            "intermediate_demand",
            "second_threshold_stats",
            ["electricity_demand", "electricity_threshold"],
        ],
    ]
    if reverse_connections:
        connections.reverse()
    demand_threshold_config["plant_config"]["technology_interconnections"] = connections

    h2i = H2IntegrateModel(demand_threshold_config)
    h2i.run()
    for variable in (
        "intermediate_demand.electricity_demand",
        "threshold_stats.electricity_threshold",
        "second_threshold_stats.electricity_threshold",
    ):
        assert h2i.prob.get_val(variable, units="MW") == pytest.approx(np.full(8760, 10.0))

    h2i.prob.set_val("electrical_load_demand.electricity_demand", 3.0, units="MW")
    h2i.prob.run_model()
    assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
        pytest.approx(np.full(8760, 3.0))
    )


@pytest.mark.unit
def test_shared_demand_profile_from_yaml(demand_threshold_config, tmp_path):
    """YAML time-series profiles initialize all connected inputs."""
    demand = demand_threshold_config["technology_config"]["technologies"]["electrical_load_demand"]
    demand["model_inputs"]["performance_parameters"]["demand_profile"] = list(range(1, 8761))
    config_path = tmp_path / "h2i_config.yaml"
    config_path.write_text(yaml.safe_dump(demand_threshold_config), encoding="utf-8")

    h2i = H2IntegrateModel(config_path)
    h2i.run()
    assert h2i.prob.get_val("threshold_stats.electricity_threshold", units="MW") == (
        pytest.approx(np.arange(1, 8761))
    )


@pytest.mark.unit
def test_invalid_shared_demand_profile_shape(demand_threshold_config):
    """A profile with the wrong length is rejected instead of silently reshaped."""
    demand = demand_threshold_config["technology_config"]["technologies"]["electrical_load_demand"]
    demand["model_inputs"]["performance_parameters"]["demand_profile"] = [1.0, 2.0]
    with pytest.raises(ValueError, match="broadcast"):
        H2IntegrateModel(demand_threshold_config)
