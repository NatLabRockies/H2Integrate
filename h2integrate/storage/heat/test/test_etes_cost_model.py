import pytest
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.storage.heat.etes_cost_model import ETESCostModel


@fixture
def petes_cost_config():
    """P-ETES cost config with placeholder linear coefficients."""
    cost_parameters = {
        "C_lin_TES": 5.0,  # $/kWh_th
        "C_const_TES": 1e6,  # $
        "C_min_TES": 1.5,  # $/kWh_th (from Table 2)
        "C_lin_ch": 100.0,  # $/kW_e
        "C_const_ch": 5e5,
        "C_lin_dis": 150.0,  # $/kW_th
        "C_const_dis": 3e5,
        "opex_fraction": 0.04,
        "cost_year": 2026,
    }
    tech_config = {"model_inputs": {"cost_parameters": cost_parameters}}
    plant_config = {"plant": {"plant_life": 30, "simulation": {"dt": 3600}}}
    return tech_config, plant_config


@fixture
def retes_cost_config():
    """R-ETES cost config: no separate charging/discharging unit costs."""
    cost_parameters = {
        "C_lin_TES": 10.0,
        "C_const_TES": 5e5,
        "C_min_TES": 3.0,
        "opex_fraction": 0.04,
        "cost_year": 2026,
    }
    tech_config = {"model_inputs": {"cost_parameters": cost_parameters}}
    plant_config = {"plant": {"plant_life": 30, "simulation": {"dt": 3600}}}
    return tech_config, plant_config


def _create_problem(tech_config, plant_config):
    prob = om.Problem()
    prob.model.add_subsystem(
        "etes_cost",
        ETESCostModel(
            tech_config=tech_config,
            plant_config=plant_config,
            driver_config={},
        ),
        promotes=["*"],
    )
    prob.setup()
    return prob


@pytest.mark.unit
class TestETESCostModel:
    def test_petes_cost_above_floor(self, petes_cost_config):
        tech_config, plant_config = petes_cost_config
        prob = _create_problem(tech_config, plant_config)

        S_TES = 1_000_000.0  # kWh
        S_ch = 100_000.0  # kW
        S_dis = 50_000.0  # kW
        prob.set_val("S_TES_kWh", S_TES)
        prob.set_val("S_ch_kW", S_ch)
        prob.set_val("S_dis_kW", S_dis)
        prob.run_model()

        params = tech_config["model_inputs"]["cost_parameters"]
        # C_lin_TES * S_TES = 5e6, floor = 1.5 * 1e6 = 1.5e6 -> linear wins
        c_tes = params["C_lin_TES"] * S_TES + params["C_const_TES"]
        c_ch = params["C_lin_ch"] * S_ch + params["C_const_ch"]
        c_dis = params["C_lin_dis"] * S_dis + params["C_const_dis"]
        expected_capex = c_tes + c_ch + c_dis
        expected_opex = params["opex_fraction"] * expected_capex

        assert prob.get_val("CapEx", units="USD")[0] == approx(expected_capex, rel=1e-9)
        assert prob.get_val("OpEx", units="USD/year")[0] == approx(expected_opex, rel=1e-9)

    def test_petes_cost_floor_active(self, petes_cost_config):
        tech_config, plant_config = petes_cost_config
        # Force a very small linear coefficient so the floor is active
        tech_config["model_inputs"]["cost_parameters"]["C_lin_TES"] = 0.1
        tech_config["model_inputs"]["cost_parameters"]["C_const_TES"] = 0.0
        prob = _create_problem(tech_config, plant_config)

        S_TES = 1_000_000.0
        prob.set_val("S_TES_kWh", S_TES)
        prob.set_val("S_ch_kW", 0.0)
        prob.set_val("S_dis_kW", 0.0)
        prob.run_model()

        # C_min_TES * S_TES = 1.5 * 1e6 = 1.5e6 (vs linear 0.1 * 1e6 = 1e5)
        params = tech_config["model_inputs"]["cost_parameters"]
        expected = params["C_min_TES"] * S_TES
        assert prob.get_val("CapEx", units="USD")[0] == approx(expected, rel=1e-9)

    def test_retes_no_ch_dis_costs(self, retes_cost_config):
        tech_config, plant_config = retes_cost_config
        prob = _create_problem(tech_config, plant_config)

        S_TES = 500_000.0
        prob.set_val("S_TES_kWh", S_TES)
        # R-ETES leaves S_ch/S_dis at zero
        prob.run_model()

        params = tech_config["model_inputs"]["cost_parameters"]
        c_tes_linear = params["C_lin_TES"] * S_TES + params["C_const_TES"]
        c_tes_floor = params["C_min_TES"] * S_TES
        expected_capex = max(c_tes_linear, c_tes_floor)

        assert prob.get_val("CapEx", units="USD")[0] == approx(expected_capex, rel=1e-9)
