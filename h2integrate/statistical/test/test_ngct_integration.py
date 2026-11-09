import numpy as np

import h2integrate


# THIS TEST VALIDATES THAT THE CASE IN EXAMPLE 38 PRODUCES THE EXPECTED STATISTICAL OUTPUTS


def test_test_testy(subtests):

    # import the configuration files and create an H2Integrate model
    total_config = {
        "name": "38_natural_gas_statistical",
        "driver_config": {
            "name": "driver_config",
            "description": "this analysis runs a brayton-cycle NG power plant with a wind plant",
            "general": {
                "folder_output": "outputs",
                "create_om_reports": True,
            },
        },
        "technology_config": {
            "name": "detailed NG plant",
            "description": "a detailed NG plant for brayton-cycle analysis",
            "technologies": {
                "ng_feedstock": {
                    "performance_model": {"model": "FeedstockPerformanceModel"},
                    "cost_model": {"model": "FeedstockCostModel"},
                    "model_inputs": {
                        "shared_parameters": {
                            "commodity": "natural_gas",
                            "commodity_rate_units": "MMBtu/h",
                        },
                        "performance_parameters": {
                            "rated_capacity": 2500.0,
                        },
                        "cost_parameters": {
                            "cost_year": 2026,
                            "price": 2.87,
                            "annual_cost": 0.0,
                            "start_up_cost": 0.0,
                        },
                    },
                },
                "natural_gas_plant": {
                    "performance_model": {"model": "SimpleCycleTurbinePerformanceModel"},
                    "cost_model": {"model": "NaturalGasCostModel"},
                    "model_inputs": {
                        "performance_parameters": {
                            "num_turbines": 1,
                            "turbine_capacity_mw": 239.0,
                            "fuel_source": "natural_gas",
                            "firing_temp_C": 1300.0,
                            "pressure_ratio": 18.712850988834695,
                            "flowrate_max_fluid_cubic_m_per_s": 477.78734437019483,
                            "isentropic_efficiency_compressor": 0.85,
                            "isentropic_efficiency_turbine": 0.9,
                            "generator_efficiency": 1.0,
                            "generator_oversize_ratio": 1.067,
                        },
                        "cost_parameters": {
                            "capex_per_kw": 2200.0,
                            "fixed_opex_per_kw_per_year": 25.6,
                            "variable_opex_per_mwh": 6.94,
                            "cost_year": 2022,
                        },
                    },
                },
                "electrical_load_demand": {
                    "performance_model": {"model": "GenericDemandComponent"},
                    "model_inputs": {
                        "performance_parameters": {
                            "commodity": "electricity",
                            "commodity_rate_units": "kW",
                            "demand_profile": 200000.0,
                        },
                    },
                },
                "output_stats": {
                    "performance_model": {"model": "ThresholdStatisticsPerformanceModel"},
                    "model_inputs": {
                        "performance_parameters": {
                            "commodity": "electricity",
                            "commodity_rate_units": "MW",
                            "commodity_amount_units": "MW*h",
                            "epsilon_comparison": 1e-06,
                        },
                    },
                },
                "headroom_stats": {
                    "performance_model": {"model": "SummaryStatisticsPerformanceModel"},
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
            "name": "brayton plant",
            "description": "a NG brayton-cycle plant serving a datacenter "
            "located somewhere in Texas",
            "sites": {
                "site": {
                    "latitude": 39.9139,
                    "longitude": -105.2135,
                    "resources": {
                        "solar_resource": {
                            "resource_model": "GOESAggregatedSolarAPI",
                            "resource_parameters": {
                                "resource_year": 2013,
                                "resource_filename": "39.9139_-105.2135_2013_"
                                "goes_aggregated_v4_60min_utc_tz.csv",
                            },
                        },
                    },
                },
            },
            "technology_interconnections": [
                ["ng_feedstock", "natural_gas_plant", "natural_gas", "pipe"],
                [
                    "electrical_load_demand",
                    "natural_gas_plant",
                    ["unmet_electricity_demand_out", "electricity_set_point"],
                ],
                ["natural_gas_plant", "output_stats", "electricity", "cable"],
                [
                    "electrical_load_demand",
                    "output_stats",
                    ["electricity_demand", "electricity_threshold"],
                ],
                ["natural_gas_plant", "headroom_stats", ["electricity_headroom", "electricity_in"]],
            ],
            "site_to_tech_connections": [
                ["site.solar_resource", "natural_gas_plant", "solar_resource_data"],
            ],
            "plant": {
                "plant_life": 30,
                "simulation": {
                    "n_timesteps": 8760,
                    "dt": 3600,
                    "start_time": "01/01 00:30:00",
                    "timezone": 0,
                },
            },
            "finance_parameters": {
                "finance_groups": {
                    "profast_lco": {
                        "finance_model": "ProFastLCO",
                        "model_inputs": {
                            "params": {
                                "analysis_start_year": 2032,
                                "installation_time": 36,
                                "inflation_rate": 0.0,
                                "discount_rate": 0.09,
                                "debt_equity_ratio": 2.62,
                                "property_tax_and_insurance": 0.03,
                                "total_income_tax_rate": 0.257,
                                "capital_gains_tax_rate": 0.15,
                                "sales_tax_rate": 0.07375,
                                "debt_interest_rate": 0.07,
                                "debt_type": "Revolving debt",
                                "loan_period_if_used": 0,
                                "cash_onhand_months": 1,
                                "admin_expense": 0.0,
                            },
                            "capital_items": {
                                "depr_type": "MACRS",
                                "depr_period": 5,
                                "refurb": [0.0],
                            },
                        },
                    },
                    "profast_npv": {
                        "finance_model": "ProFastNPV",
                        "model_inputs": {
                            "commodity_sell_price": 0.0,
                            "commodity_sell_price_units": "USD/kW/h",
                            "params": {
                                "analysis_start_year": 2032,
                                "installation_time": 36,
                                "inflation_rate": 0.0,
                                "discount_rate": 0.09,
                                "debt_equity_ratio": 2.62,
                                "property_tax_and_insurance": 0.03,
                                "total_income_tax_rate": 0.257,
                                "capital_gains_tax_rate": 0.15,
                                "sales_tax_rate": 0.07375,
                                "debt_interest_rate": 0.07,
                                "debt_type": "Revolving debt",
                                "loan_period_if_used": 0,
                                "cash_onhand_months": 1,
                                "admin_expense": 0.0,
                            },
                            "capital_items": {
                                "depr_type": "MACRS",
                                "depr_period": 5,
                                "refurb": [0.0],
                            },
                        },
                    },
                },
                "finance_subgroups": {
                    "natural_gas": {
                        "commodity": "electricity",
                        "commodity_stream": "natural_gas_plant",
                        "finance_groups": ["profast_lco"],
                        "technologies": ["natural_gas_plant", "ng_feedstock"],
                    },
                    "electricity": {
                        "commodity": "electricity",
                        "commodity_stream": "natural_gas_plant",
                        "use_commodity_stream_timeseries": True,
                        "commodity_stream_output": "electricity_out",
                        "finance_groups": "profast_lco",
                        "technologies": ["natural_gas_plant", "ng_feedstock"],
                    },
                },
                "cost_adjustment_parameters": {
                    "cost_year_adjustment_inflation": 0.025,
                    "target_dollar_year": 2022,
                },
            },
        },
    }
    h2i = h2integrate.H2IntegrateModel(total_config)

    # these are needed to ensure functional input-input connections
    h2i.model.connect(
        "electrical_load_demand.electricity_demand",
        "output_stats.electricity_threshold",
    )
    h2i.model.set_input_defaults(
        "electrical_load_demand.electricity_demand",
        val=[
            total_config["technology_config"]["technologies"]["electrical_load_demand"][
                "model_inputs"
            ]["performance_parameters"]["demand_profile"]
            for _ in range(total_config["plant_config"]["plant"]["simulation"]["n_timesteps"])
        ],
        units=total_config["technology_config"]["technologies"]["electrical_load_demand"][
            "model_inputs"
        ]["performance_parameters"]["commodity_rate_units"],
    )

    # run the model
    h2i.run()

    # check on a reference value against the model outputs
    ref_values_outputs = {
        "output_stats.net_electricity_surplus": {
            "value": 0.004554999988130248,
            "units": "MW*h",
            "rtol": 1.0e-4,
        },  # MWh
        "output_stats.net_electricity_deficit": {
            "value": 55491.37392665059,
            "units": "MW*h",
            "rtol": 1.0e-4,
        },  # MWh
        "output_stats.ratio_timestep_electricity_surplus": {
            "value": 0.5199771689497716,
            "units": None,
            "rtol": 1.0e-4,
        },  # fraction
        "output_stats.ratio_timestep_electricity_deficit": {
            "value": 0.4800228310502284,
            "units": None,
            "rtol": 1.0e-4,
        },  # fraction
    }
    ref_values_headroom = {
        "headroom_stats.electricity_min": {"value": 0.0, "units": "MW", "rtol": 1.0e-4},
        "headroom_stats.electricity_median": {"value": 1.10458218, "units": "MW", "rtol": 1.0e-4},
        "headroom_stats.electricity_mean": {"value": 7.16543, "units": "MW", "rtol": 1.0e-4},
        "headroom_stats.electricity_max": {"value": 43.67380725, "units": "MW", "rtol": 1.0e-4},
        "headroom_stats.electricity_percentiles": {
            "value": [0.00, 0.00, 0.00, 1.10458218, 17.29011199, 25.71392898, 30.30195342],
            "units": "MW",
            "rtol": 1.0e-4,
        },
    }

    # iterate over reference values and compare with model outputs
    for key, ref_val in {**ref_values_outputs, **ref_values_headroom}.items():
        model_val = h2i.model.get_val(key, units=ref_val["units"])
        print(f"DEBUG!!!!! {ref_val}, model_val: {model_val}")
        with subtests.test(msg=f"statistics check for {key}"):
            assert np.allclose(model_val, ref_val["value"], rtol=ref_val.get("rtol")), (
                f"Mismatch for {key}: expected {ref_val['value']}"
                f"{' ' + ref_val['units'] if ref_val['units'] else ''}, got {model_val}"
            )
