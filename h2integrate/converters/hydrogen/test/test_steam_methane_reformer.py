import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.hydrogen.steam_methane_reformer import (
    SteamMethaneReformerCostModel,
    SteamMethaneReformerPerformanceModel,
)


@fixture
def smr_performance_params():
    "H2 SMR performance parameters."
    tech_params = {
        "system_capacity_tonnes_per_day": 240.0,  # 10,000 kg/h
        "natural_gas_usage_mmbtu_per_kg": 0.192,
        "electricity_usage_kwh_per_kg": 0.88,
    }
    return tech_params


@fixture
def smr_cost_params():
    "H2 SMR cost parameters."
    cost_params = {
        "capex_per_kw": 500.0,
        "fixed_opex_per_kw_per_year": 20.0,
        "variable_opex_per_kwh": 0.05,
        "cost_year": 2020,
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


@pytest.mark.unit
def test_h2_smr_performance_outputs(plant_config, smr_performance_params, subtests):
    """Test SMR performance model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": smr_performance_params,
        }
    }

    # Create a simple natural gas input profile (constant 1920 MMBtu/h for 10000 kg/h plant)
    natural_gas_input = np.full(8760, 1920.0)  # MMBtu/h
    electricity_input = np.full(8760, 8800.0)  # kWh/h (0.88 kWh/kg * 10,000 kg/h)

    prob = om.Problem()
    perf_comp = SteamMethaneReformerPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("comp", perf_comp, promotes=["*"])
    prob.setup()

    # Set the natural gas input and electricity input
    prob.set_val("comp.natural_gas_in", natural_gas_input)
    prob.set_val("comp.electricity_in", electricity_input)
    prob.run_model()

    commodity = "hydrogen"
    commodity_amount_units = "kg"
    commodity_rate_units = "kg/h"
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

    # Test output values
    with subtests.test("hydrogen_out value"):
        assert (
            pytest.approx(np.sum(prob.get_val("comp.hydrogen_out", units="kg/h")), rel=1e-6)
            == 10000.0 * 8760
        )
    with subtests.test("natural_gas_consumed value"):
        assert (
            pytest.approx(
                np.sum(prob.get_val("comp.natural_gas_consumed", units="MMBtu/h")), rel=1e-6
            )
            == 1920.0 * 8760
        )
    with subtests.test("electricity_consumed value"):
        assert (
            pytest.approx(np.sum(prob.get_val("comp.electricity_consumed", units="kW")), rel=1e-6)
            == 8800.0 * 8760
        )
    with subtests.test("rated_hydrogen_production value"):
        assert (
            pytest.approx(prob.get_val("comp.rated_hydrogen_production", units="kg/h"), rel=1e-6)
            == 10000.0
        )
    with subtests.test("electrical_rated_hydrogen_production value"):
        assert (
            pytest.approx(
                prob.get_val("comp.electrical_rated_hydrogen_production", units="MW"), rel=1e-6
            )
            == 571.49645
        )
    with subtests.test("total_hydrogen_produced value"):
        assert (
            pytest.approx(prob.get_val("comp.total_hydrogen_produced", units="kg"), rel=1e-6)
            == 10000.0 * 8760
        )
    with subtests.test("capacity_factor value"):
        assert pytest.approx(prob.get_val("comp.capacity_factor", units="unitless"), rel=1e-6) == 1

    with subtests.test("annual_hydrogen_produced value"):
        assert (
            pytest.approx(prob.get_val("comp.annual_hydrogen_produced", units="kg/yr"), rel=1e-6)
            == 10000.0 * 8760
        )


@pytest.mark.regression
def test_h2_smr_cost(smr_performance_params, smr_cost_params, plant_config, subtests):
    """Test SMR cost model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": smr_performance_params,
            "cost_parameters": smr_cost_params,
        }
    }

    # Set the natural gas input and electricity input
    natural_gas_input = np.full(8760, 1920.0)
    electricity_input = np.full(8760, 8800.0)

    prob = om.Problem()
    perf_comp = SteamMethaneReformerPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    cost_comp = SteamMethaneReformerCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("comp", perf_comp, promotes=["*"])
    prob.model.add_subsystem("cost_comp", cost_comp, promotes=["*"])
    prob.setup()

    # Set the natural gas input and electricity input
    prob.set_val("comp.natural_gas_in", natural_gas_input)
    prob.set_val("comp.electricity_in", electricity_input)
    prob.run_model()

    with subtests.test("capex value"):
        assert pytest.approx(prob.get_val("cost_comp.CapEx", units="USD"), rel=1e-6) == (
            571.49645 * 1000.0 * 500.0
        )

    with subtests.test("opex value"):
        assert pytest.approx(prob.get_val("cost_comp.OpEx", units="USD/year"), rel=1e-6) == (
            571.49645 * 1000.0 * 20.0  # fixed opex
        )

    with subtests.test("var opex value"):
        assert pytest.approx(prob.get_val("cost_comp.VarOpEx", units="USD/year"), rel=1e-6) == (
            250315447.17  # variable opex
        )
