import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.nitrogen.simple_ASU import SimpleASUCostModel, SimpleASUPerformanceModel


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,  # Default number of timesteps for the simulation
                "dt": 3600,
            },
        },
    }
    return plant_config


def test_simple_ASU_performance_model_outputs(plant_config, subtests):
    """Test user-defined capacity in kW and user input electricity profile"""
    p_max_kW = 1000.0
    e_profile_in_kW = np.tile(np.linspace(0.0, p_max_kW * 1.2, 876), 10)
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": {
                "size_from_N2_demand": False,
                "ASU_rated_power_kW": p_max_kW,
                "efficiency_kWh_pr_kg_N2": 0.119,
            },
        }
    }

    prob = om.Problem()
    comp = SimpleASUPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp)
    prob.setup()

    # Set dummy electricity input
    prob.set_val("comp.electricity_in", e_profile_in_kW.tolist(), units="kW")
    prob.run_model()

    commodity = "nitrogen"
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


def test_simple_ASU_performance_model_set_capacity_kW(plant_config, subtests):
    """Test user-defined capacity in kW and user input electricity profile"""
    p_max_kW = 1000.0
    e_profile_in_kW = np.tile(np.linspace(0.0, p_max_kW * 1.2, 876), 10)
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": {
                "size_from_N2_demand": False,
                "ASU_rated_power_kW": p_max_kW,
                "efficiency_kWh_pr_kg_N2": 0.119,
            },
        }
    }
    prob = om.Problem()
    comp = SimpleASUPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("asu_perf", comp)
    prob.setup()

    # Set dummy electricity input
    prob.set_val("asu_perf.electricity_in", e_profile_in_kW.tolist(), units="kW")
    prob.run_model()
    # Dummy expected values
    max_n2_mfr = prob.get_val("asu_perf.rated_nitrogen_production", units="kg/h")[0]
    max_pwr_kw = prob.get_val("asu_perf.ASU_capacity_kW")[0]
    max_eff = max_pwr_kw / max_n2_mfr

    with subtests.test("max/rated efficiency"):
        assert pytest.approx(max_eff, rel=1e-6) == comp.config.efficiency_kWh_pr_kg_N2

    with subtests.test("max N2 production"):
        assert max(prob.get_val("asu_perf.nitrogen_out")) <= max_n2_mfr

    with subtests.test("annual electricity usage"):
        assert max(prob.get_val("asu_perf.annual_electricity_consumption")) <= sum(e_profile_in_kW)


def test_simple_ASU_performance_model_size_for_demand(plant_config, subtests):
    """Test user-defined capacity in kW and user input electricity profile"""
    n2_dmd_max_kg_pr_hr = 1000.0
    n2_dmd_kg_pr_hr = np.tile(np.linspace(0.0, n2_dmd_max_kg_pr_hr, 876), 10)
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": {
                "size_from_N2_demand": True,
                "efficiency_kWh_pr_kg_N2": 0.119,
            },
        }
    }
    prob = om.Problem()
    asu_perf = SimpleASUPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("asu_perf", asu_perf)
    prob.setup()

    # Set dummy nitrogen demand profile
    prob.set_val("asu_perf.nitrogen_in", n2_dmd_kg_pr_hr.tolist(), units="kg/h")
    prob.run_model()
    # Dummy expected values
    max_n2_mfr = prob.get_val("asu_perf.rated_nitrogen_production", units="kg/h")[0]
    max_pwr_kw = prob.get_val("asu_perf.ASU_capacity_kW")[0]
    max_eff = max_pwr_kw / max_n2_mfr

    with subtests.test("max/rated efficiency"):
        assert pytest.approx(max_eff, rel=1e-6) == asu_perf.config.efficiency_kWh_pr_kg_N2

    with subtests.test("max N2 production"):
        assert max(prob.get_val("asu_perf.nitrogen_out")) <= max_n2_mfr

    with subtests.test("max electricity usage"):
        assert max(prob.get_val("asu_perf.electricity_in")) <= max_pwr_kw

    with subtests.test("nitrogen produced does not exceed nitrogen demand"):
        assert all(
            x <= y
            for x, y in zip(
                prob.get_val("asu_perf.nitrogen_out"), prob.get_val("asu_perf.nitrogen_in")
            )
        )


def test_simple_ASU_cost_model_usd_pr_kw(plant_config, subtests):
    capex_usd_per_kw = 10.0
    opex_usd_per_kw = 5.0

    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": {
                "capex_usd_per_unit": capex_usd_per_kw,  # dummy number
                "capex_unit": "kw",
                "opex_usd_per_unit_per_year": opex_usd_per_kw,  # dummy number
                "opex_unit": "kw",
                "cost_year": 2022,
            },
        }
    }

    efficiency_kWh_per_kg = 0.119
    rated_power_kW = 1000.0
    rated_N2_mfr = rated_power_kW / efficiency_kWh_per_kg
    prob = om.Problem()
    comp = SimpleASUCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("asu_cost", comp)
    prob.setup()

    # Set required inputs
    prob.set_val("asu_cost.ASU_capacity_kW", rated_power_kW, units="kW")
    prob.set_val("asu_cost.rated_nitrogen_production", rated_N2_mfr, units="kg/h")
    prob.run_model()

    expected_outputs = {
        "CapEx": [rated_power_kW * capex_usd_per_kw],
        "OpEx": [rated_power_kW * opex_usd_per_kw],
    }

    for out, expected in expected_outputs.items():
        with subtests.test(out):
            val = prob.get_val(f"asu_cost.{out}")
            assert pytest.approx(val, rel=1e-6) == expected[0]


def test_simple_ASU_cost_model_usd_pr_mw(plant_config, subtests):
    capex_usd_per_kw = 10.0
    opex_usd_per_kw = 5.0
    capex_usd_per_mw = capex_usd_per_kw * 1e3
    opex_usd_per_mw = opex_usd_per_kw * 1e3
    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": {
                "capex_usd_per_unit": capex_usd_per_mw,  # dummy number
                "capex_unit": "mw",
                "opex_usd_per_unit_per_year": opex_usd_per_mw,  # dummy number
                "opex_unit": "mw",
                "cost_year": 2022,
            },
        }
    }

    efficiency_kWh_per_kg = 0.119
    rated_power_kW = 1000.0
    rated_N2_mfr = rated_power_kW / efficiency_kWh_per_kg
    prob = om.Problem()
    comp = SimpleASUCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("asu_cost", comp)
    prob.setup()

    # Set required inputs
    prob.set_val("asu_cost.ASU_capacity_kW", rated_power_kW, units="kW")
    prob.set_val("asu_cost.rated_nitrogen_production", rated_N2_mfr, units="kg/h")
    prob.run_model()

    expected_outputs = {
        "CapEx": [rated_power_kW * capex_usd_per_kw],
        "OpEx": [rated_power_kW * opex_usd_per_kw],
    }

    for out, expected in expected_outputs.items():
        with subtests.test(out):
            val = prob.get_val(f"asu_cost.{out}")
            assert pytest.approx(val, rel=1e-6) == expected[0]


def test_simple_ASU_performance_and_cost_size_for_demand(plant_config, subtests):
    """Test user-defined capacity in kW and user input electricity profile"""
    cpx_usd_per_mw = 10.0  # dummy number
    opex_usd_per_mw = 5.0  # dummy number
    n2_dmd_max_kg_pr_hr = 1000.0
    n2_dmd_kg_pr_hr = np.tile(np.linspace(0.0, n2_dmd_max_kg_pr_hr, 876), 10)
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": {
                "size_from_N2_demand": True,
                "efficiency_kWh_pr_kg_N2": 0.119,
            },
            "cost_parameters": {
                "capex_usd_per_unit": cpx_usd_per_mw,  # dummy number
                "capex_unit": "mw",
                "opex_usd_per_unit_per_year": opex_usd_per_mw,  # dummy number
                "opex_unit": "mw",
                "cost_year": 2022,
            },
        }
    }
    prob = om.Problem()
    asu_perf = SimpleASUPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    asu_cost = SimpleASUCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("asu_perf", asu_perf, promotes=["*"])
    prob.model.add_subsystem("asu_cost", asu_cost, promotes=["*"])
    prob.setup()

    # Set dummy nitrogen demand profile
    prob.set_val("asu_perf.nitrogen_in", n2_dmd_kg_pr_hr.tolist(), units="kg/h")
    prob.run_model()
    # Dummy expected values
    max_n2_mfr = prob.get_val("asu_perf.rated_nitrogen_production")[0]
    max_pwr_kw = prob.get_val("asu_perf.ASU_capacity_kW")[0]
    max_eff = max_pwr_kw / max_n2_mfr

    with subtests.test("max/rated efficiency"):
        assert pytest.approx(max_eff, rel=1e-6) == asu_perf.config.efficiency_kWh_pr_kg_N2

    with subtests.test("max N2 production"):
        assert max(prob.get_val("asu_perf.nitrogen_out")) <= max_n2_mfr

    with subtests.test("max electricity usage"):
        assert max(prob.get_val("asu_perf.electricity_in")) <= max_pwr_kw

    with subtests.test("nitrogen produced does not exceed nitrogen demand"):
        assert all(
            x <= y
            for x, y in zip(
                prob.get_val("asu_perf.nitrogen_out"), prob.get_val("asu_perf.nitrogen_in")
            )
        )

    with subtests.test("CapEx"):
        assert (
            pytest.approx(prob.get_val("asu_cost.CapEx")[0], rel=1e-6)
            == max_pwr_kw * cpx_usd_per_mw / 1e3
        )

    with subtests.test("OpEx"):
        assert (
            pytest.approx(prob.get_val("asu_cost.OpEx")[0], rel=1e-6)
            == max_pwr_kw * opex_usd_per_mw / 1e3
        )
