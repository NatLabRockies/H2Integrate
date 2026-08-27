import importlib

import numpy as np
import pytest

from h2integrate import H2IntegrateModel


@pytest.mark.regression
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_demo_case(subtests):
    # Create an H2I model
    driver_config = {
        "name": "driver_config",
        "description": "this analysis runs a brayton-cycle NG power plant",
        "general": {"folder_output": "outputs"},
    }
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
                # "cost_model": {
                #     "model": "NaturalGasCostModel",
                # },
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
                },
            },
        },
    }
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
        "resource_to_tech_connections": [
            ["site.solar_resource", "ng", "solar_resource_data"],
        ],
    }

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
        "natural_gas_consumed": 1928.089814235099,  # MMBtu/h
        "electricity_out": 216.2495760842288,  # MW
    }

    with subtests.test("config_value_fuel_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.fuel_source
            == ref_values["fuel_source"]
        )

    with subtests.test("config_value_capacity_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.turbine_capacity_mw
            == ref_values["turbine_capacity"]
        )
        assert (
            h2i.model.get_val("ng.turbine_capacity", units="MW") == ref_values["turbine_capacity"]
        )

    with subtests.test("config_value_firing_temp_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.firing_temp_C
            == ref_values["firing_temp_C"]
        )

    with subtests.test("config_value_pressure_ratio_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.pressure_ratio
            == ref_values["pressure_ratio"]
        )

    with subtests.test("config_value_volumetric_flowerate_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.flowrate_max_fluid_cubic_m_per_s
            == ref_values["flowrate_max_fluid_cubic_m_per_s"]
        )
        assert (
            h2i.model.get_val("ng.flowrate_max_fluid", units="m**3/s")
            == ref_values["flowrate_max_fluid_cubic_m_per_s"]
        )

    with subtests.test("config_value_isen_eff_comp_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.isentropic_efficiency_compressor
            == ref_values["isentropic_efficiency_compressor"]
        )

    with subtests.test("config_value_isen_eff_turb_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.isentropic_efficiency_turbine
            == ref_values["isentropic_efficiency_turbine"]
        )

    with subtests.test("config_value_eff_gen_set"):
        assert (
            h2i.model.plant.ng.SimpleCycleTurbinePerformanceModel.config.generator_efficiency
            == ref_values["generator_efficiency"]
        )

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
