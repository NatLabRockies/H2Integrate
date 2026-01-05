import numpy as np
import pytest
import openmdao.api as om

from h2integrate.converters.nitrogen.simple_ASU import SimpleASUCostModel, SimpleASUPerformanceModel


plant_config = {
    "plant": {
        "plant_life": 30,
        "simulation": {
            "n_timesteps": 8760,  # Default number of timesteps for the simulation
            "dt": 3600,
        },
    },
}


def test_simple_ASU_performance_model_set_capacity_kW(subtests):
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
    prob.set_val("asu_perf.electricity_in", e_profile_in_kW.tolist(), units="kW*h")
    prob.run_model()
    # Dummy expected values
    max_n2_mfr = prob.get_val("asu_perf.rated_N2_kg_pr_hr")[0]
    max_pwr_kw = prob.get_val("asu_perf.ASU_capacity_kW")[0]
    max_eff = max_pwr_kw / max_n2_mfr

    with subtests.test("max/rated efficiency"):
        assert pytest.approx(max_eff, rel=1e-6) == comp.config.efficiency_kWh_pr_kg_N2

    with subtests.test("max N2 production"):
        assert max(prob.get_val("asu_perf.nitrogen_out")) <= max_n2_mfr

    with subtests.test("annual electricity usage"):
        assert max(prob.get_val("asu_perf.annual_electricity_consumption")) <= sum(e_profile_in_kW)


def test_simple_ASU_performance_model_size_for_demand(subtests):
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
    max_n2_mfr = prob.get_val("asu_perf.rated_N2_kg_pr_hr")[0]
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


def test_simple_ASU_cost_model_usd_pr_kw(subtests):
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
    prob.set_val("asu_cost.rated_N2_kg_pr_hr", rated_N2_mfr, units="kg/h")
    prob.run_model()

    expected_outputs = {
        "CapEx": [rated_power_kW * capex_usd_per_kw],
        "OpEx": [rated_power_kW * opex_usd_per_kw],
    }

    for out, expected in expected_outputs.items():
        with subtests.test(out):
            val = prob.get_val(f"asu_cost.{out}")
            assert pytest.approx(val, rel=1e-6) == expected[0]


def test_simple_ASU_cost_model_usd_pr_mw(subtests):
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
    prob.set_val("asu_cost.rated_N2_kg_pr_hr", rated_N2_mfr, units="kg/h")
    prob.run_model()

    expected_outputs = {
        "CapEx": [rated_power_kW * capex_usd_per_kw],
        "OpEx": [rated_power_kW * opex_usd_per_kw],
    }

    for out, expected in expected_outputs.items():
        with subtests.test(out):
            val = prob.get_val(f"asu_cost.{out}")
            assert pytest.approx(val, rel=1e-6) == expected[0]


def test_simple_ASU_performance_and_cost_size_for_demand(subtests):
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
    max_n2_mfr = prob.get_val("asu_perf.rated_N2_kg_pr_hr")[0]
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
