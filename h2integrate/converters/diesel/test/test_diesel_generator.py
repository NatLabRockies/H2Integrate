import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.diesel.diesel_generator import (
    DieselGeneratorCostModel,
    DieselGeneratorPerformanceModel,
)


@fixture
def diesel_performance_params():
    """Diesel generator performance parameters."""
    tech_params = {
        "heat_rate_gal_per_mwh": 75.0,  # gal/MWh - typical for modern diesel gen
        "system_capacity_kw": 5000.0,  # 5 MW in kW
    }
    return tech_params


@fixture
def diesel_cost_params():
    """Diesel generator cost parameters."""
    cost_params = {
        "capex_per_kw": 900,  # $/kW
        "fixed_opex_per_kw_per_year": 20.0,  # $/kW/year
        "variable_opex_per_kwh": 0.008,  # $/kWh (excluding fuel)
        "system_capacity_kw": 5000.0,  # 5 MW in kW
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
                "n_timesteps": 48,
                "dt": 3600,
            },
        },
    }


@pytest.mark.unit
def test_diesel_performance_outputs(plant_config, diesel_performance_params, subtests):
    """Test diesel generator performance model output structure and bounds."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": diesel_performance_params,
        }
    }

    # Constant diesel input sized to run the 5 MW plant at rated capacity
    # (5 MW * 75 gal/MWh = 375 gal/h)
    diesel_input = np.full(48, 375.0)  # gal/h

    prob = om.Problem()
    perf_comp = DieselGeneratorPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("diesel_test", perf_comp, promotes=["*"])
    prob.setup()

    prob.set_val("diesel_test.diesel_in", diesel_input, units="galUS/h")
    prob.run_model()

    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    with subtests.test("0 <= replacement_schedule <= 1"):
        assert np.all(prob.get_val("diesel_test.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("diesel_test.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("diesel_test.replacement_schedule", units="unitless")) == plant_life

    with subtests.test("0 <= capacity_factor (unitless) <= 1"):
        assert np.all(prob.get_val("diesel_test.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("diesel_test.capacity_factor", units="unitless") <= 1)

    with subtests.test("1 <= capacity_factor (percent) <= 100"):
        assert np.all(prob.get_val("diesel_test.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("diesel_test.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("diesel_test.capacity_factor", units="unitless")) == plant_life

    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"diesel_test.rated_{commodity}_production", units=commodity_rate_units)
            > 0
        )

    with subtests.test(f"rated_{commodity}_production length"):
        assert (
            len(
                prob.get_val(
                    f"diesel_test.rated_{commodity}_production", units=commodity_rate_units
                )
            )
            == 1
        )

    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"diesel_test.total_{commodity}_produced", units=commodity_amount_units)
            > 0
        )
    with subtests.test(f"total_{commodity}_produced length"):
        assert (
            len(
                prob.get_val(
                    f"diesel_test.total_{commodity}_produced", units=commodity_amount_units
                )
            )
            == 1
        )

    with subtests.test(f"annual_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(
                f"diesel_test.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
            )
            > 0
        )

    with subtests.test(f"annual_{commodity}_produced[1:] == annual_{commodity}_produced[0]"):
        annual_production = prob.get_val(
            f"diesel_test.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"annual_{commodity}_produced length"):
        assert len(annual_production) == plant_life

    with subtests.test(f"Some of {commodity}_out > 0"):
        assert np.any(prob.get_val(f"diesel_test.{commodity}_out", units=commodity_rate_units) > 0)

    with subtests.test(f"{commodity}_out length"):
        assert (
            len(prob.get_val(f"diesel_test.{commodity}_out", units=commodity_rate_units))
            == n_timesteps
        )

    with subtests.test("operational_life default value"):
        assert prob.get_val("diesel_test.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("diesel_test.replacement_schedule", units="unitless") == 0)


@pytest.mark.unit
def test_diesel_performance(plant_config, diesel_performance_params, subtests):
    """Test diesel generator performance model with fuel-limited dispatch."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": diesel_performance_params,
        }
    }

    # 5 MW * 75 gal/MWh = 375 gal/h to run at rated capacity
    diesel_input = np.full(48, 375.0)  # gal/h

    prob = om.Problem()
    perf_comp = DieselGeneratorPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("diesel_perf", perf_comp, promotes=["*"])
    prob.setup()

    prob.set_val("diesel_in", diesel_input, units="galUS/h")
    prob.run_model()

    electricity_out = prob.get_val("electricity_out", units="MW")

    with subtests.test("Diesel Electricity Output"):
        expected_output = diesel_input / diesel_performance_params["heat_rate_gal_per_mwh"]
        assert pytest.approx(electricity_out, rel=1e-6) == expected_output

    with subtests.test("Diesel Average Output"):
        # electricity_out is retrieved in MW; capacity is stored in kW
        assert (
            pytest.approx(np.mean(electricity_out), rel=1e-6)
            == diesel_performance_params["system_capacity_kw"] / 1000.0
        )


@pytest.mark.unit
def test_diesel_cost(plant_config, diesel_cost_params, subtests):
    """Test diesel generator cost model calculations."""
    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": diesel_cost_params,
        }
    }

    system_capacity_kw = 5000.0  # 5 MW in kW
    annual_generation_kWh = 20_000_000  # ~46% capacity factor (20 GWh)

    # Hourly electricity output in kW that sums to annual generation
    electricity_out = np.full(48, annual_generation_kWh / 8760)  # kW

    prob = om.Problem()
    cost_comp = DieselGeneratorCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("diesel_cost", cost_comp, promotes=["*"])
    prob.setup()

    prob.set_val("system_capacity_kw", system_capacity_kw, units="kW")
    prob.set_val("electricity_out", electricity_out, units="kW")
    prob.run_model()

    capex = prob.get_val("CapEx", units="USD")[0]
    opex = prob.get_val("OpEx", units="USD/year")[0]
    cost_year = prob.get_val("cost_year")

    expected_capex = diesel_cost_params["capex_per_kw"] * system_capacity_kw
    expected_fixed_om = diesel_cost_params["fixed_opex_per_kw_per_year"] * system_capacity_kw
    expected_variable_om = diesel_cost_params["variable_opex_per_kwh"] * sum(electricity_out)
    expected_opex = expected_fixed_om + expected_variable_om

    with subtests.test("Diesel Capital Cost"):
        assert pytest.approx(capex, rel=1e-6) == expected_capex

    with subtests.test("Diesel Operating Cost"):
        assert pytest.approx(opex, rel=1e-6) == expected_opex

    with subtests.test("Diesel Cost Year"):
        assert cost_year == diesel_cost_params["cost_year"]


@pytest.mark.unit
def test_diesel_performance_demand(plant_config, diesel_performance_params, subtests):
    """Test diesel generator dispatch against a time-varying electricity command."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": diesel_performance_params,
        }
    }

    # Ample fuel supply so dispatch is set-point limited, not fuel limited
    diesel_input = np.full(48, 375.0)  # galUS/h (enough for full rated capacity)
    system_capacity_kw = diesel_performance_params["system_capacity_kw"]
    electricity_demand_section = np.linspace(0, 1.2 * system_capacity_kw, 12)
    electricity_demand_kw = np.tile(electricity_demand_section, 4)

    prob = om.Problem()
    perf_comp = DieselGeneratorPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("diesel_perf", perf_comp, promotes=["*"])
    prob.setup()

    prob.set_val("diesel_in", diesel_input, units="galUS/h")
    prob.set_val("electricity_command_value", electricity_demand_kw, units="kW")
    prob.run_model()

    electricity_out = prob.get_val("electricity_out", units="kW")

    with subtests.test("Diesel Electricity Output"):
        expected_output_fuel = diesel_input / diesel_performance_params["heat_rate_gal_per_mwh"]
        expected_output_elec = np.where(
            electricity_demand_kw > system_capacity_kw,
            system_capacity_kw,
            electricity_demand_kw,
        )
        expected_output = np.minimum(expected_output_fuel * 1000, expected_output_elec)
        assert pytest.approx(electricity_out, rel=1e-6) == expected_output

    with subtests.test("Diesel Max Output clipped to system capacity"):
        assert pytest.approx(np.max(electricity_out), rel=1e-6) == system_capacity_kw

    with subtests.test("Unmet demand equals command minus output"):
        unmet = prob.get_val("unmet_electricity_demand", units="kW")
        assert pytest.approx(unmet, rel=1e-6, abs=1e-9) == electricity_demand_kw - electricity_out
