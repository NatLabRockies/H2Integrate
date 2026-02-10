import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.natural_gas.natural_gas_cc_ct import (
    NaturalGasCostModel,
    NaturalGasPerformanceModel,
)


@fixture
def ngcc_performance_params():
    """Natural Gas Combined Cycle performance parameters."""
    tech_params = {
        "heat_rate_mmbtu_per_mwh": 7.5,  # MMBtu/MWh - typical for NGCC
        "system_capacity_mw": 100,
    }
    return tech_params


@fixture
def ngct_performance_params():
    """Natural Gas Combustion Turbine performance parameters."""
    tech_params = {
        "heat_rate_mmbtu_per_mwh": 11.5,  # MMBtu/MWh - typical for NGCT
        "system_capacity_mw": 50,
    }
    return tech_params


@fixture
def ngcc_cost_params():
    """Natural Gas Combined Cycle cost parameters."""
    cost_params = {
        "capex_per_kw": 1000,  # $/kW
        "fixed_opex_per_kw_per_year": 10.0,  # $/kW/year
        "variable_opex_per_mwh": 2.5,  # $/MWh
        "heat_rate_mmbtu_per_mwh": 7.5,  # MMBtu/MWh
        "system_capacity_mw": 100,  # MW
        "cost_year": 2023,
    }
    return cost_params


@fixture
def ngct_cost_params():
    """Natural Gas Combustion Turbine cost parameters."""
    cost_params = {
        "capex_per_kw": 800,  # $/kW
        "fixed_opex_per_kw_per_year": 8.0,  # $/kW/year
        "variable_opex_per_mwh": 3.0,  # $/MWh
        "heat_rate_mmbtu_per_mwh": 11.5,  # MMBtu/MWh
        "system_capacity_mw": 100,  # MW
        "cost_year": 2023,
    }
    return cost_params


@fixture
def plant_config():
    """Fixture to get plant configuration."""
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }


def test_ngcc_performance_outputs(plant_config, ngcc_performance_params, subtests):
    """Test NGCC performance model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": ngcc_performance_params,
        }
    }

    # Create a simple natural gas input profile (constant 750 MMBtu/h for 100 MW plant)
    natural_gas_input = np.full(8760, 750.0)  # MMBtu

    prob = om.Problem()
    perf_comp = NaturalGasPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("comp", perf_comp, promotes=["*"])
    prob.setup()

    # Set the natural gas input
    prob.set_val("comp.natural_gas_in", natural_gas_input)
    prob.run_model()

    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    # Check that replacement schedule is between 0 and 1
    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    # Check that capacity factor is between 0 and 1 with units of "unitless"
    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") <= 1)

    # Check that capacity factor is between 1 and 100 with units of "percent"
    with subtests.test("1 <= capacity_factor (percent) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("comp.capacity_factor", units="unitless")) == plant_life

    # Test that rated commodity production is greater than zero
    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units) > 0
        )

    with subtests.test(f"rated_{commodity}_production length"):
        assert (
            len(prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units)) == 1
        )

    # Test that total commodity production is greater than zero
    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units) > 0
        )
    with subtests.test(f"total_{commodity}_produced length"):
        assert (
            len(prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units)) == 1
        )

    # Test that annual commodity production is greater than zero
    with subtests.test(f"annual_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr")
            > 0
        )

    with subtests.test(f"annual_{commodity}_produced[1:] == annual_{commodity}_produced[0]"):
        annual_production = prob.get_val(
            f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"annual_{commodity}_produced length"):
        assert len(annual_production) == plant_life

    # Test that commodity output has some values greater than zero
    with subtests.test(f"Some of {commodity}_out > 0"):
        assert np.any(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units) > 0)

    with subtests.test(f"{commodity}_out length"):
        assert len(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units)) == n_timesteps

    # Test default values
    with subtests.test("operational_life default value"):
        assert prob.get_val("comp.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


def test_ngcc_performance(plant_config, ngcc_performance_params, subtests):
    """Test NGCC performance model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": ngcc_performance_params,
        }
    }

    # Create a simple natural gas input profile (constant 750 MMBtu/h for 100 MW plant)
    natural_gas_input = np.full(8760, 750.0)  # MMBtu

    prob = om.Problem()
    perf_comp = NaturalGasPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("ng_perf", perf_comp, promotes=["*"])
    prob.setup()

    # Set the natural gas input
    prob.set_val("natural_gas_in", natural_gas_input)
    prob.run_model()

    electricity_out = prob.get_val("electricity_out")

    with subtests.test("NGCC Electricity Output"):
        # Expected: 750 MMBtu / 7.5 MMBtu/MWh = 100 MW
        expected_output = natural_gas_input / ngcc_performance_params["heat_rate_mmbtu_per_mwh"]
        assert pytest.approx(electricity_out, rel=1e-6) == expected_output

    with subtests.test("NGCC Average Output"):
        # Check average output is 100 MW
        assert pytest.approx(np.mean(electricity_out), rel=1e-6) == 100.0


def test_ngct_performance(plant_config, ngct_performance_params, subtests):
    """Test NGCT performance model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": ngct_performance_params,
        }
    }

    # Create a simple natural gas input profile (constant 575 MMBtu/h for 50 MW plant)
    natural_gas_input = np.full(8760, 575.0)  # MMBtu

    prob = om.Problem()
    perf_comp = NaturalGasPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("ng_perf", perf_comp, promotes=["*"])
    prob.setup()

    # Set the natural gas input
    prob.set_val("natural_gas_in", natural_gas_input)
    prob.run_model()

    electricity_out = prob.get_val("electricity_out")

    with subtests.test("NGCT Electricity Output"):
        # Expected: 575 MMBtu / 11.5 MMBtu/MWh = 50 MW
        expected_output = natural_gas_input / ngct_performance_params["heat_rate_mmbtu_per_mwh"]
        assert pytest.approx(electricity_out, rel=1e-6) == expected_output

    with subtests.test("NGCT Average Output"):
        # Check average output is 50 MW
        assert pytest.approx(np.mean(electricity_out), rel=1e-6) == 50.0


def test_ngcc_cost(plant_config, ngcc_cost_params, subtests):
    """Test NGCC cost model calculations."""
    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": ngcc_cost_params,
        }
    }

    # Plant parameters for a 100 MW NGCC plant
    system_capacity = 100.0  # 100 MW
    annual_generation_MWh = 700_000  # ~80% capacity factor

    # Create hourly electricity output that sums to annual generation
    electricity_out = np.full(8760, annual_generation_MWh / 8760)  # MW

    prob = om.Problem()
    cost_comp = NaturalGasCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("ng_cost", cost_comp, promotes=["*"])
    prob.setup()

    # Set inputs
    prob.set_val("system_capacity", system_capacity)
    prob.set_val("electricity_out", electricity_out)
    prob.run_model()

    capex = prob.get_val("CapEx")[0]
    opex = prob.get_val("OpEx")[0]
    cost_year = prob.get_val("cost_year")

    # Calculate expected values
    expected_capex = ngcc_cost_params["capex_per_kw"] * system_capacity * 1000.0
    expected_fixed_om = ngcc_cost_params["fixed_opex_per_kw_per_year"] * system_capacity * 1000.0
    expected_variable_om = ngcc_cost_params["variable_opex_per_mwh"] * annual_generation_MWh
    expected_opex = expected_fixed_om + expected_variable_om

    with subtests.test("NGCC Capital Cost"):
        assert pytest.approx(capex, rel=1e-6) == expected_capex

    with subtests.test("NGCC Operating Cost"):
        assert pytest.approx(opex, rel=1e-6) == expected_opex

    with subtests.test("NGCC Cost Year"):
        assert cost_year == ngcc_cost_params["cost_year"]


def test_ngct_cost(plant_config, ngct_cost_params, subtests):
    """Test NGCT cost model calculations."""
    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": ngct_cost_params,
        }
    }

    # Plant parameters for a 50 MW NGCT plant
    system_capacity = 50.0  # 50 MW
    annual_generation_MWh = 100_000  # ~23% capacity factor (peaking plant)

    # Create hourly electricity output that sums to annual generation
    electricity_out = np.full(8760, annual_generation_MWh / 8760)  # MW

    prob = om.Problem()
    cost_comp = NaturalGasCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("ng_cost", cost_comp, promotes=["*"])
    prob.setup()

    # Set inputs
    prob.set_val("system_capacity", system_capacity)
    prob.set_val("electricity_out", electricity_out)
    prob.run_model()

    capex = prob.get_val("CapEx")[0]
    opex = prob.get_val("OpEx")[0]
    cost_year = prob.get_val("cost_year")

    # Calculate expected values
    expected_capex = ngct_cost_params["capex_per_kw"] * system_capacity * 1000.0
    expected_fixed_om = ngct_cost_params["fixed_opex_per_kw_per_year"] * system_capacity * 1000.0
    expected_variable_om = ngct_cost_params["variable_opex_per_mwh"] * annual_generation_MWh
    expected_opex = expected_fixed_om + expected_variable_om

    with subtests.test("NGCT Capital Cost"):
        assert pytest.approx(capex, rel=1e-6) == expected_capex

    with subtests.test("NGCT Operating Cost"):
        assert pytest.approx(opex, rel=1e-6) == expected_opex

    with subtests.test("NGCT Cost Year"):
        assert cost_year == ngct_cost_params["cost_year"]


def test_ngcc_performance_demand(plant_config, ngcc_performance_params, subtests):
    """Test NGCC performance model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": ngcc_performance_params,
        }
    }

    # Create a simple natural gas input profile (constant 750 MMBtu/h for 100 MW plant)
    natural_gas_input = np.full(8760, 750.0)  # MMBtu
    electricity_demand_section = np.linspace(
        0, 1.2 * ngcc_performance_params["system_capacity_mw"], 12
    )
    electricity_demand_MW = np.tile(electricity_demand_section, 730)

    prob = om.Problem()
    perf_comp = NaturalGasPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("ng_perf", perf_comp, promotes=["*"])
    prob.setup()

    # Set the natural gas input
    prob.set_val("natural_gas_in", natural_gas_input)
    prob.set_val("electricity_demand", electricity_demand_MW)
    prob.run_model()

    electricity_out = prob.get_val("electricity_out")

    with subtests.test("NGCC Electricity Output"):
        # Expected: 750 MMBtu / 7.5 MMBtu/MWh = 100 MW
        expected_output_ng = natural_gas_input / ngcc_performance_params["heat_rate_mmbtu_per_mwh"]
        expected_output_elec = np.where(
            electricity_demand_MW > ngcc_performance_params["system_capacity_mw"],
            ngcc_performance_params["system_capacity_mw"],
            electricity_demand_MW,
        )
        expected_output = np.minimum.reduce([expected_output_ng, expected_output_elec])
        assert pytest.approx(electricity_out, rel=1e-6) == expected_output

    with subtests.test("NGCC Max Output"):
        # Check average output is 100 MW
        assert (
            pytest.approx(np.max(electricity_out), rel=1e-6)
            == ngcc_performance_params["system_capacity_mw"]
        )
