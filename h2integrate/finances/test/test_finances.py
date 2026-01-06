import copy
import unittest
from pathlib import Path

import pytest
import openmdao.api as om
from pytest import approx

from h2integrate.finances.profast_lco import ProFastLCO
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml, load_driver_yaml


examples_dir = Path(__file__).resolve().parent.parent.parent.parent / "examples/."


class TestProFastComp(unittest.TestCase):
    def setUp(self):
        self.plant_config = {
            "finance_parameters": {
                "finance_model": "ProFastComp",
                "model_inputs": {
                    "params": {
                        "analysis_start_year": 2022,
                        "installation_time": 24,
                        "inflation_rate": 0.02,
                        "discount_rate": 0.08,
                        "debt_equity_ratio": 2.3333333333333335,
                        "property_tax_and_insurance": 0.015,
                        "total_income_tax_rate": 0.21,
                        "capital_gains_tax_rate": 0.15,
                        "sales_tax_rate": 0.07,
                        "debt_interest_rate": 0.05,
                        "debt_type": "Revolving debt",
                        "loan_period_if_used": 10,
                        "cash_onhand_months": 6,
                        "admin_expense": 0.03,
                    },
                    "capital_items": {
                        "depr_type": "Straight line",
                        "depr_period": 20,
                    },
                },
                "cost_adjustment_parameters": {
                    "target_dollar_year": 2022,
                    "cost_year_adjustment_inflation": 0.0,
                },
            },
            "plant": {
                "plant_life": 30,
                "grid_connection": True,
                "ppa_price": 0.05,
            },
            "policy_parameters": {
                "electricity_itc": 0.3,
                "h2_storage_itc": 0.3,
                "electricity_ptc": 25,
                "h2_ptc": 3,
            },
        }

        self.tech_config = {
            "electrolyzer": {
                "model_inputs": {
                    "financial_parameters": {
                        "capital_items": {
                            "depr_period": 10,
                            "replacement_cost_percent": 0.1,
                        }
                    }
                }
            },
        }

        self.driver_config = {"general": {}}

    def test_electrolyzer_refurb_results(self):
        prob = om.Problem()

        # change name of tech to make sure that the refurb works with names
        # that contain, not just match "electrolyzer"
        edited_tech_config = {"electrolyzer1": copy.deepcopy(self.tech_config["electrolyzer"])}

        comp = ProFastLCO(
            plant_config=self.plant_config,
            tech_config=edited_tech_config,
            driver_config=self.driver_config,
            commodity_type="hydrogen",
        )
        ivc = om.IndepVarComp()
        ivc.add_output("total_hydrogen_produced", 4.0e5, units="kg/year")
        prob.model.add_subsystem("ivc", ivc, promotes=["*"])
        prob.model.add_subsystem("comp", comp, promotes=["*"])

        prob.setup()

        prob.set_val("capex_adjusted_electrolyzer1", 1.0e7, units="USD")
        prob.set_val("opex_adjusted_electrolyzer1", 1.0e4, units="USD/year")

        prob.set_val("electrolyzer1_time_until_replacement", 5.0e3, units="h")

        prob.run_model()

        self.assertAlmostEqual(prob["LCOH"][0], 4.27529137, places=7)

    def test_modified_lcoe_calc(self):
        # Set up paths
        example_case_dir = examples_dir / "01_onshore_steel_mn"

        tech_config = load_tech_yaml(example_case_dir / "tech_config.yaml")
        plant_config = load_plant_yaml(example_case_dir / "plant_config.yaml")
        driver_config = load_driver_yaml(example_case_dir / "driver_config.yaml")
        finance_inputs = plant_config["finance_parameters"]["finance_groups"].pop("profast_model")
        plant_config_filtered = {k: v for k, v in plant_config.items() if k != "finance_parameters"}
        plant_config_filtered.update({"finance_parameters": finance_inputs})
        # Run ProFastComp with loaded configs
        prob = om.Problem()
        comp = ProFastLCO(
            plant_config=plant_config_filtered,
            tech_config=tech_config["technologies"],
            driver_config=driver_config,
            commodity_type="electricity",
        )
        ivc = om.IndepVarComp()
        ivc.add_output("total_electricity_produced", 2.0e7, units="kW*h/year")
        prob.model.add_subsystem("ivc", ivc, promotes=["*"])
        prob.model.add_subsystem("comp", comp, promotes=["*"])

        prob.setup()

        prob.set_val("capex_adjusted_hopp", 2.0e7, units="USD")
        prob.set_val("opex_adjusted_hopp", 2.0e4, units="USD/year")
        prob.set_val("capex_adjusted_electrolyzer", 1.0e7, units="USD")
        prob.set_val("opex_adjusted_electrolyzer", 1.0e4, units="USD/year")
        prob.set_val("capex_adjusted_h2_storage", 5.0e6, units="USD")
        prob.set_val("opex_adjusted_h2_storage", 5.0e3, units="USD/year")
        prob.set_val("capex_adjusted_steel", 3.0e6, units="USD")
        prob.set_val("opex_adjusted_steel", 3.0e3, units="USD/year")
        prob.set_val("electrolyzer_time_until_replacement", 80000.0, units="h")

        prob.run_model()

        self.assertAlmostEqual(prob["LCOE"][0], 0.2116038814767319, places=7)

    def test_lcoe_with_selected_technologies(self):
        # Set up paths
        example_case_dir = examples_dir / "01_onshore_steel_mn"

        tech_config = load_tech_yaml(example_case_dir / "tech_config.yaml")
        plant_config = load_plant_yaml(example_case_dir / "plant_config.yaml")
        driver_config = load_driver_yaml(example_case_dir / "driver_config.yaml")

        # Only include HOPP and electrolyzer in metrics
        plant_config["finance_parameters"]["finance_subgroups"]["electricity"]["technologies"] = [
            "hopp",
            "steel",
        ]
        finance_inputs = plant_config["finance_parameters"]["finance_groups"].pop("profast_model")
        plant_config_filtered = {k: v for k, v in plant_config.items() if k != "finance_parameters"}
        plant_config_filtered.update({"finance_parameters": finance_inputs})

        prob = om.Problem()
        comp = ProFastLCO(
            plant_config=plant_config_filtered,
            tech_config=tech_config["technologies"],
            driver_config=driver_config,
            commodity_type="electricity",
        )
        ivc = om.IndepVarComp()
        ivc.add_output("total_electricity_produced", 2.0e7, units="kW*h/year")
        prob.model.add_subsystem("ivc", ivc, promotes=["*"])
        prob.model.add_subsystem("comp", comp, promotes=["*"])

        prob.setup()

        prob.set_val("capex_adjusted_hopp", 2.0e7, units="USD")
        prob.set_val("opex_adjusted_hopp", 2.0e4, units="USD/year")
        prob.set_val("capex_adjusted_electrolyzer", 1.0e7, units="USD")
        prob.set_val("opex_adjusted_electrolyzer", 1.0e4, units="USD/year")
        prob.set_val("capex_adjusted_h2_storage", 5.0e6, units="USD")
        prob.set_val("opex_adjusted_h2_storage", 5.0e3, units="USD/year")
        prob.set_val("capex_adjusted_steel", 3.0e6, units="USD")
        prob.set_val("opex_adjusted_steel", 3.0e3, units="USD/year")
        prob.set_val("electrolyzer_time_until_replacement", 80000.0, units="h")

        prob.run_model()

        self.assertAlmostEqual(prob["LCOE"][0], 0.2116038814767319, places=6)


def test_profast_config_provided():
    """Test that inputting ProFAST parameters gives same LCOH as specifying finance
    parameters directly (as is done in `test_electrolyzer_refurb_results`). Output
    based on output from `test_electrolyzer_refurb_results()` at time of writing.
    """

    pf_params = {
        "installation_time": 24,
        "analysis_start_year": 2024,
        "inflation_rate": 0.02,
        "demand rampup": 0,
        "operating life": 30,
        "installation months": 24,
        "TOPC": {"unit price": 0.0, "decay": 0.0, "support utilization": 0.0, "sunset years": 0},
        "commodity": {"name": "Hydrogen", "unit": "kg", "initial price": 100, "escalation": 0.02},
        "annual operating incentive": {
            "value": 0.0,
            "decay": 0.0,
            "sunset years": 0,
            "taxable": True,
        },
        "incidental revenue": {"value": 0.0, "escalation": 0.0},
        "credit card fees": 0,
        "sales tax": 0.07,
        "road tax": {"value": 0.0, "escalation": 0.0},
        "labor": {"value": 0.0, "rate": 0.0, "escalation": 0.0},
        "maintenance": {"value": 0, "escalation": 0.02},
        "rent": {"value": 0, "escalation": 0.02},
        "license and permit": {"value": 0, "escalation": 0.02},
        "non depr assets": 0.0,
        "end of proj sale non depr assets": 0.0,
        "installation cost": {
            "value": 0,
            "depr type": "Straight line",
            "depr period": 4,
            "depreciable": False,
        },
        "one time cap inct": {
            "value": 0.0,
            "depr type": "MACRS",
            "depr period": 3,
            "depreciable": True,
        },
        "property tax and insurance": 0.015,
        "admin expense": 0.03,
        "tax loss carry forward years": 0,
        "capital gains tax rate": 0.15,
        "tax losses monetized": True,
        "sell undepreciated cap": True,
        "loan period if used": 10,
        "debt equity ratio of initial financing": 2.3333333333333335,
        "debt interest rate": 0.05,
        "debt type": "Revolving debt",
        "total income tax rate": 0.21,
        "cash onhand": 6,
        "general inflation rate": 0.02,
        "leverage after tax nominal discount rate": 0.08,
    }
    plant_config = {
        "finance_parameters": {
            "finance_model": "ProFastComp",
            "model_inputs": {
                "params": pf_params,
                "capital_items": {
                    "depr_type": "Straight line",
                    "depr_period": 20,
                },
            },
            "cost_adjustment_parameters": {
                "target_dollar_year": 2022,
                "cost_year_adjustment_inflation": 0.0,
            },
        },
        "plant": {
            "plant_life": 30,
            "cost_year": 2022,
            "grid_connection": True,
            "ppa_price": 0.05,
        },
        "policy_parameters": {
            "electricity_itc": 0.3,
            "h2_storage_itc": 0.3,
            "electricity_ptc": 25,
            "h2_ptc": 3,
        },
    }

    tech_config = {
        "electrolyzer": {
            "model_inputs": {
                "financial_parameters": {
                    "capital_items": {
                        "depr_period": 10,
                        "replacement_cost_percent": 0.1,
                    }
                }
            }
        },
    }

    driver_config = {"general": {}}

    prob = om.Problem()
    comp = ProFastLCO(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config=driver_config,
        commodity_type="hydrogen",
    )
    ivc = om.IndepVarComp()
    ivc.add_output("total_hydrogen_produced", 4.0e5, units="kg/year")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    prob.setup()

    prob.set_val("capex_adjusted_electrolyzer", 1.0e7, units="USD")
    prob.set_val("opex_adjusted_electrolyzer", 1.0e4, units="USD/year")

    prob.set_val("electrolyzer_time_until_replacement", 5.0e3, units="h")

    prob.run_model()

    assert prob["LCOH"] == approx(4.27529137)


def test_parameter_validation_clashing_values():
    """Test that parameter validation raises an error when plant config and params
    have different values for the same parameter."""

    # Create plant config with clashing values
    pf_params = {
        "installation_time": 24,  # Different from installation_months
        "installation months": 12,  # Different from installation_time (24)
        "inflation_rate": 0.0,
        "analysis start year": 2023,
        "operating life": 25,  # Different from plant config (30)
        "commodity": {"name": "Hydrogen", "unit": "kg", "initial price": 100, "escalation": 0.02},
        "general inflation rate": 0.0,
        "admin_expense": 0.0,
        "capital_gains_tax_rate": 0.15,
        "sales_tax_rate": 0.07,
        "debt_interest_rate": 0.05,
        "debt_type": "Revolving debt",
        "loan_period_if_used": 10,
        "cash_onhand_months": 6,
        "property_tax_and_insurance": 0.03,
        "discount_rate": 0.09,
        "debt_equity_ratio": 1.62,
        "total_income_tax_rate": 0.25,
    }

    plant_config = {
        "finance_parameters": {
            "finance_model": "ProFastComp",
            "model_inputs": {
                "params": pf_params,
                "capital_items": {
                    "depr_type": "Straight line",
                    "depr_period": 20,
                },
            },
            "cost_adjustment_parameters": {
                "target_dollar_year": 2022,
                "cost_year_adjustment_inflation": 0.0,
            },
        },
        "plant": {
            "plant_life": 30,  # Different from pf_params
        },
    }

    tech_config = {
        "electrolyzer": {
            "model_inputs": {
                "financial_parameters": {
                    "capital_items": {
                        "depr_period": 10,
                        "replacement_cost_percent": 0.1,
                    }
                }
            }
        },
    }

    driver_config = {"general": {}}

    prob = om.Problem()
    comp = ProFastLCO(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config=driver_config,
        commodity_type="hydrogen",
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    # Should raise ValueError during setup due to clashing values for installation
    with pytest.raises(ValueError, match="Inconsistent values provided"):
        prob.setup()

    # check that it works for just operating life
    plant_config["finance_parameters"]["model_inputs"]["params"].pop("installation months")
    prob = om.Problem()
    comp = ProFastLCO(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config=driver_config,
        commodity_type="hydrogen",
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    # Should raise ValueError during setup due to clashing values
    with pytest.raises(ValueError, match="Inconsistent values provided"):
        prob.setup()


def test_parameter_validation_duplicate_parameters():
    """Test that parameter validation raises an error when plant config and pf_params
    have different values for the same parameter."""

    # Create plant config with clashing values
    pf_params = {
        "analysis_start_year": 2024,  # Different from pf_params
        "installation_time": 24,  # Different from installation_months
        "inflation_rate": 0.0,
        "analysis start year": 2023,  # Different from plant config (2024)
        "operating life": 25,  # Different from plant config (30)
        "installation months": 12,  # Different from installation_time (24)
        "commodity": {"name": "Hydrogen", "unit": "kg", "initial price": 100, "escalation": 0.02},
        "general inflation rate": 0.0,
        "admin_expense": 0.0,
        "capital_gains_tax_rate": 0.15,
        "sales_tax_rate": 0.07,
        "debt_interest_rate": 0.05,
        "debt_type": "Revolving debt",
        "loan_period_if_used": 10,
        "cash_onhand_months": 6,
        "property_tax_and_insurance": 0.03,
        "discount_rate": 0.09,
        "debt_equity_ratio": 1.62,
        "total_income_tax_rate": 0.25,
    }

    plant_config = {
        "finance_parameters": {
            "finance_model": "ProFastComp",
            "model_inputs": {
                "params": pf_params,
                "capital_items": {
                    "depr_type": "Straight line",
                    "depr_period": 20,
                },
            },
            "cost_adjustment_parameters": {
                "target_dollar_year": 2022,
                "cost_year_adjustment_inflation": 0.0,
            },
        },
        "plant": {
            "plant_life": 30,  # Different from pf_params
        },
    }

    tech_config = {
        "electrolyzer": {
            "model_inputs": {
                "financial_parameters": {
                    "capital_items": {
                        "depr_period": 10,
                        "replacement_cost_percent": 0.1,
                    }
                }
            }
        },
    }

    driver_config = {"general": {}}

    prob = om.Problem()
    comp = ProFastLCO(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config=driver_config,
        commodity_type="hydrogen",
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    # Should raise ValueError during setup due to clashing values
    with pytest.raises(ValueError, match="Duplicate entries found in ProFastComp params"):
        prob.setup()
