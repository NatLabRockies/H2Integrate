import importlib

import numpy as np
import pytest
import openmdao.api as om

from h2integrate import H2IntegrateModel


@pytest.fixture
def driver_config():
    driver_config = {
        "name": "driver_config",
        "description": "this analysis runs a brayton-cycle NG power plant",
        "general": {"folder_output": "outputs"},
    }
    return driver_config


@pytest.fixture
def technology_config(use_reliability):
    technology_config = {
        "name": "detailed NG plant",
        "description": "a detailed NG plant for brayton-cycle analysis",
        "technologies": {
            "ng_feedstock": {
                "performance_model": {
                    "model": "FeedstockPerformanceModel",
                },
                "cost_model": {
                    "model": "FeedstockCostModel",
                },
                "model_inputs": {
                    "shared_parameters": {
                        "commodity": "natural_gas",
                        "commodity_rate_units": "MMBtu/h",
                    },
                    "performance_parameters": {
                        "rated_capacity": 3000.0,
                    },
                    "cost_parameters": {
                        "cost_year": 2023,
                        "commodity_amount_units": "MMBtu",
                        "price": 4.2,
                        "annual_cost": 0.0,
                        "start_up_cost": 100000.0,
                    },
                },
            },
            "ng": {
                "performance_model": {
                    "model": "SimpleCycleTurbinePerformanceModel",
                },
                "model_inputs": {
                    "performance_parameters": {
                        "fuel_source": "natural_gas",
                        "num_turbines": 1,
                        "turbine_capacity_mw": 239.0,
                        "firing_temp_C": 1300.0,
                        "pressure_ratio": 18.712850988834695,
                        "flowrate_max_fluid_cubic_m_per_s": 477.78734437019483,
                        "isentropic_efficiency_compressor": 0.85,
                        "isentropic_efficiency_turbine": 0.90,
                        "generator_efficiency": 1.0,
                        "generator_oversize_ratio": 1.067,  # (300 MVA @ 0.85 PF = 255 MW)/239 MW
                    },
                    "cost_parameters": {
                        "capex_per_kw": 1000,  # $/kW - typical for NGCC; stolen from ex. 16
                        "fixed_opex_per_kw_per_year": 10.0,  # $/kW/year; stolen from ex. 16
                        "variable_opex_per_mwh": 2.5,  # $/MWh; stolen from ex. 16
                        "cost_year": 2023,  # stolen from ex. 16
                    },
                    "reliability": {
                        "use_reliability": use_reliability,
                        "availability_type": "minimum",
                        "burn_in": 6.5,
                        "failure_model": "WeibullReliability",
                        "maintenance_model": "FixedIntervalReliability",
                        "failure_parameters": {
                            "scale": 0.5,
                            "shape": 1,
                            "n_components": 3,
                            "downtime": {
                                "model": "FixedDowntime",
                                "hours": 5,
                                "n_components": 3,
                            },
                        },
                        "maintenance_parameters": {
                            "frequency": [0.25, 1, 4],
                            "downtime": {
                                "model": "UniformDowntime",
                                "min_hours": 2,
                                "max_hours": 5,
                                "n_components": 3,
                            },
                        },
                    },
                },
            },
        },
    }
    return technology_config


@pytest.fixture
def plant_config():
    plant_config = {
        "name": "brayton plant",
        "description": "a brayton-cycle plant located somewhere in Texas",
        "sites": {
            "site": {
                "latitude": 34.382308,
                "longitude": -101.816607,
                "resources": {
                    "solar_resource": {
                        "resource_model": "GOESAggregatedSolarAPI",
                        "resource_parameters": {
                            "resource_year": 2024,
                            "resource_filename": "30.6617_-101.7096_psmv3_60_2013.csv",
                        },
                    },
                },
            },
        },
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
        "technology_interconnections": [
            ["ng_feedstock", "ng", "natural_gas", "pipe"],
        ],
        "site_to_tech_connections": [
            ["site.solar_resource", "ng", "solar_resource_data"],
        ],
    }
    return plant_config


@pytest.fixture
def ref_values(use_reliability):
    electricity_out = 214.84743476692168 if use_reliability else 216.2495760842288
    natural_gas_consumed = 1915.626506141986 if use_reliability else 1928.089814235099
    ref_values = {
        "fuel_source": "natural_gas",
        "turbine_capacity": 239.0,
        "firing_temp_C": 1300.0,
        "pressure_ratio": 18.712850988834695,
        "flowrate_max_fluid_cubic_m_per_s": 477.78734437019483,
        "isentropic_efficiency_compressor": 0.85,
        "isentropic_efficiency_turbine": 0.90,
        "generator_efficiency": 1.0,
        "electricity_set_point": 1.0e9,  # MW, default value
        "natural_gas_in": 3000.0,  # MMBtu/h
        "natural_gas_consumed": natural_gas_consumed,  # MMBtu/h
        "electricity_out": electricity_out,  # MW
    }
    return ref_values


@pytest.mark.regression
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
@pytest.mark.parametrize(
    "use_reliability",
    [False, True],
    ids=["Simple Cycle w/o Reliability", "Simple Cycle w Reliability"],
)
def test_demo_case(
    subtests, use_reliability, plant_config, technology_config, driver_config, ref_values
):
    h2i = H2IntegrateModel(
        {
            "name": "brayton",
            "system_summary": "a Brayton-cycle NG plant sim using real time ambient condition data",
            "driver_config": driver_config,
            "technology_config": technology_config,
            "plant_config": plant_config,
        }
    )

    # Run the model
    h2i.run()

    # Post-process the results
    h2i.post_process()

    simple_turbine = h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel
    n_turb = simple_turbine.get_val("num_turbines")
    with subtests.test("'use_reliability' is fed correctly"):
        assert simple_turbine.use_reliability is use_reliability
        if use_reliability:
            assert simple_turbine.availability.shape[0] == np.ceil(n_turb)
            assert not np.all(np.unique(simple_turbine.availability.sum(axis=0)) != n_turb)
        else:
            assert np.all(simple_turbine.availability == 1)

    with subtests.test("config_value_fuel_set"):
        assert simple_turbine.config.fuel_source == ref_values["fuel_source"]

    with subtests.test("config_value_capacity_set"):
        assert simple_turbine.config.turbine_capacity_mw == ref_values["turbine_capacity"]
        assert (
            h2i.model.get_val("ng.turbine_capacity", units="MW") == ref_values["turbine_capacity"]
        )

    with subtests.test("config_value_firing_temp_set"):
        assert simple_turbine.config.firing_temp_C == ref_values["firing_temp_C"]

    with subtests.test("config_value_pressure_ratio_set"):
        assert simple_turbine.config.pressure_ratio == ref_values["pressure_ratio"]

    with subtests.test("config_value_volumetric_flowerate_set"):
        assert (
            simple_turbine.config.flowrate_max_fluid_cubic_m_per_s
            == ref_values["flowrate_max_fluid_cubic_m_per_s"]
        )
        assert (
            h2i.model.get_val("ng.flowrate_max_fluid", units="m**3/s")
            == ref_values["flowrate_max_fluid_cubic_m_per_s"]
        )

    with subtests.test("config_value_isen_eff_comp_set"):
        assert (
            simple_turbine.config.isentropic_efficiency_compressor
            == ref_values["isentropic_efficiency_compressor"]
        )

    with subtests.test("config_value_isen_eff_turb_set"):
        assert (
            simple_turbine.config.isentropic_efficiency_turbine
            == ref_values["isentropic_efficiency_turbine"]
        )

    with subtests.test("config_value_eff_gen_set"):
        assert simple_turbine.config.generator_efficiency == ref_values["generator_efficiency"]

    with subtests.test("input_value_controller_set_point_value"):
        assert np.all(
            h2i.model.get_val("ng.electricity_set_point", units="MW")
            == ref_values["electricity_set_point"]
        )

    with subtests.test("input_value_plant_command_value"):
        assert np.all(
            h2i.model.get_val("ng.electricity_command_value", units="MW")
            == ref_values["electricity_set_point"]
        )

    with subtests.test("input_value_natural_gas_feed"):
        assert np.all(
            h2i.model.get_val("ng.natural_gas_in", units="MMBtu/h") == ref_values["natural_gas_in"]
        )

    with subtests.test("output_value_elec_out"):
        assert np.mean(h2i.model.get_val("ng.electricity_out", units="MW")) == pytest.approx(
            ref_values["electricity_out"], rel=1.0e-6
        )

    with subtests.test("output_value_rated_elec"):
        assert (
            np.mean(h2i.model.get_val("ng.rated_electricity_production", units="MW"))
            == ref_values["turbine_capacity"]
        )

    with subtests.test("output_value_ng_consumption"):
        assert np.mean(
            h2i.model.get_val("ng.natural_gas_consumed", units="MMBtu/h")
        ) == pytest.approx(ref_values["natural_gas_consumed"], rel=1.0e-6)


@pytest.fixture
def turbine_problem_factory(plant_config, technology_config, driver_config, tmp_path, monkeypatch):
    from h2integrate.converters.combustion_machines.turbine_simple_cycle import (
        SimpleCycleTurbinePerformanceModel,
    )

    monkeypatch.chdir(tmp_path)
    n_timesteps = 500
    plant_config["plant"]["simulation"]["n_timesteps"] = n_timesteps
    tech_config = technology_config["technologies"]["ng"]

    def make_problem(reliability=None):
        if reliability is not None:
            tech_config["model_inputs"]["reliability"] = reliability
        problem = om.Problem()
        problem.model.add_subsystem(
            "turbine",
            SimpleCycleTurbinePerformanceModel(
                driver_config=driver_config, plant_config=plant_config, tech_config=tech_config
            ),
            promotes=["*"],
        )
        problem.setup()
        problem.set_val(
            "solar_resource_data",
            {
                "temperature": np.full(n_timesteps, 20.0),
                "pressure": np.full(n_timesteps, 1013.25),
            },
        )
        problem.set_val("natural_gas_in", np.full(n_timesteps, 1.0e9))
        problem.set_val("electricity_command_value", np.full(n_timesteps, 1.0e9))
        return problem

    return make_problem


@pytest.mark.unit
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
@pytest.mark.parametrize("use_reliability", [False])
def test_multiple_turbines_scale_fuel_and_electricity(turbine_problem_factory):
    problem = turbine_problem_factory()
    problem.run_model()
    single_fuel = problem.get_val("natural_gas_consumed").copy()
    single_electricity = problem.get_val("electricity_out").copy()

    problem.set_val("num_turbines", 2)
    problem.run_model()

    assert np.all(single_fuel > 0)
    np.testing.assert_allclose(problem.get_val("natural_gas_consumed"), 2 * single_fuel)
    np.testing.assert_allclose(problem.get_val("electricity_out"), 2 * single_electricity)


@pytest.mark.unit
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
@pytest.mark.parametrize("use_reliability", [True])
@pytest.mark.parametrize(
    "downtime",
    [
        {"model": "FixedDowntime", "hours": 5},
        {"model": "UniformDowntime", "min_hours": 2, "max_hours": 5},
    ],
    ids=["fixed-downtime", "uniform-downtime"],
)
def test_multiple_turbines_sample_independent_reproducible_availability(
    turbine_problem_factory, downtime
):
    reliability = {
        "use_reliability": True,
        "availability_type": "minimum",
        "failure_model": "WeibullReliability",
        "failure_parameters": {"scale": 0.02, "shape": 1, "downtime": downtime},
    }
    problem = turbine_problem_factory(reliability)
    problem.set_val("num_turbines", 2)
    problem.run_model()
    availability = problem.model.turbine.availability.copy()
    electricity = problem.get_val("electricity_out").copy()
    fuel = problem.get_val("natural_gas_consumed").copy()

    assert availability.shape == (2, 500)
    assert np.any(availability == 0)
    assert not np.array_equal(availability[0], availability[1])
    available_turbines = availability.sum(axis=0)
    assert np.any(available_turbines == 1)
    fully_available = np.flatnonzero(available_turbines == 2)[0]
    np.testing.assert_allclose(electricity, electricity[fully_available] * available_turbines / 2)
    np.testing.assert_allclose(fuel, fuel[fully_available] * available_turbines / 2)

    problem.run_model()
    np.testing.assert_array_equal(problem.model.turbine.availability, availability)
    np.testing.assert_allclose(problem.get_val("electricity_out"), electricity)
    np.testing.assert_allclose(problem.get_val("natural_gas_consumed"), fuel)

    problem.set_val("num_turbines", 3)
    problem.run_model()
    np.testing.assert_array_equal(problem.model.turbine.availability[:2], availability)
