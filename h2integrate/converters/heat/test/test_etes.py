import numpy as np
import openmdao.api as om
import pytest
from pytest import approx, fixture

from h2integrate.converters.heat.etes import ETESPerformanceModel


@fixture
def petes_config():
    """P-ETES (decoupled) configuration using parameter values from Table 2."""
    performance_parameters = {
        "etes_type": "P-ETES",
        "S_TES_kWh": 1_000_000.0,  # 1 GWh thermal storage
        "S_ch_kW": 100_000.0,  # 100 MW electric charging
        "S_dis_kW": 50_000.0,  # 50 MW thermal discharging
        "eta_ch": 0.95,
        "eta_dis": 0.73,
        "f_loss": 0.0068,
        "SOC_min": 0.0,
        "SOC_init": 0.5,
        "cost_year": 2026,
    }
    n = 24
    plant_config = {
        "plant": {"simulation": {"n_timesteps": n, "dt": 3600}},
    }
    tech_config = {"model_inputs": {"performance_parameters": performance_parameters}}
    return tech_config, plant_config, n


@fixture
def retes_config():
    """R-ETES (integrated) configuration using parameter values from Table 3."""
    performance_parameters = {
        "etes_type": "R-ETES",
        "S_TES_kWh": 1_000_000.0,
        "eta_ch": 0.98,
        "eta_dis": 0.90,
        "f_loss": 0.0068,
        "f_ch_max": 0.3,
        "f_dis_max": 0.2,
        "SOC_min": 0.0,
        "SOC_init": 0.5,
        "cost_year": 2026,
    }
    n = 24
    plant_config = {
        "plant": {"simulation": {"n_timesteps": n, "dt": 3600}},
    }
    tech_config = {"model_inputs": {"performance_parameters": performance_parameters}}
    return tech_config, plant_config, n


def _create_problem(tech_config, plant_config):
    prob = om.Problem()
    prob.model.add_subsystem(
        "etes",
        ETESPerformanceModel(
            tech_config=tech_config,
            plant_config=plant_config,
            driver_config={},
        ),
        promotes=["*"],
    )
    prob.setup()
    return prob


@pytest.mark.unit
class TestETESPerformanceModel:
    def test_petes_discharge_meets_load(self, petes_config):
        tech_config, plant_config, n = petes_config
        prob = _create_problem(tech_config, plant_config)

        # No charging electricity, constant thermal load well below discharge cap
        load = np.full(n, 10_000.0)  # 10 MW_th
        prob.set_val("electricity_in_kW", np.zeros(n))
        prob.set_val("heat_demand_kW", load)
        prob.run_model()

        heat_out = prob.get_val("heat_out_kW", units="kW")
        unmet = prob.get_val("unmet_heat_demand_kW", units="kW")
        E_st = prob.get_val("E_st_kWh", units="kW*h")

        # Discharge should fully meet load since storage is half-full
        assert heat_out == approx(load, rel=1e-6)
        assert unmet == approx(np.zeros(n), abs=1e-6)
        # Storage should monotonically decrease
        assert np.all(np.diff(E_st) <= 0)

    def test_petes_charging_rate_limited(self, petes_config):
        tech_config, plant_config, n = petes_config
        prob = _create_problem(tech_config, plant_config)

        # Massive electricity input, no load. Charging should be capped at
        # S_ch * eta_ch = 100_000 * 0.95 = 95_000 kW_th into storage.
        prob.set_val("electricity_in_kW", np.full(n, 1e9))
        prob.set_val("heat_demand_kW", np.zeros(n))
        prob.run_model()

        Q_ch = prob.get_val("Q_ch_kW", units="kW")
        S_ch_kW = tech_config["model_inputs"]["performance_parameters"]["S_ch_kW"]
        eta_ch = tech_config["model_inputs"]["performance_parameters"]["eta_ch"]
        cap = S_ch_kW * eta_ch
        # Either capped by S_ch * eta_ch or by remaining headroom in storage
        assert np.all(Q_ch <= cap + 1e-6)
        # In early timesteps before storage fills, should hit the cap
        assert Q_ch[0] == approx(cap, rel=1e-6)

    def test_petes_discharge_rate_limited(self, petes_config):
        tech_config, plant_config, n = petes_config
        # Start full so we have plenty of energy
        tech_config["model_inputs"]["performance_parameters"]["SOC_init"] = 1.0
        prob = _create_problem(tech_config, plant_config)

        # Huge load, no charging
        prob.set_val("electricity_in_kW", np.zeros(n))
        prob.set_val("heat_demand_kW", np.full(n, 1e9))
        prob.run_model()

        heat_out = prob.get_val("heat_out_kW", units="kW")
        # Should be capped at S_dis_kW = 50_000 kW_th
        S_dis_kW = tech_config["model_inputs"]["performance_parameters"]["S_dis_kW"]
        assert heat_out[0] == approx(S_dis_kW, rel=1e-6)

    def test_petes_energy_balance(self, petes_config):
        tech_config, plant_config, n = petes_config
        prob = _create_problem(tech_config, plant_config)

        rng = np.random.default_rng(0)
        elec_in = rng.uniform(0, 80_000, n)
        load = rng.uniform(0, 30_000, n)
        prob.set_val("electricity_in_kW", elec_in)
        prob.set_val("heat_demand_kW", load)
        prob.run_model()

        E_st = prob.get_val("E_st_kWh", units="kW*h")
        Q_ch = prob.get_val("Q_ch_kW", units="kW")
        Q_dis = prob.get_val("Q_dis_kW", units="kW")
        Q_st_loss = prob.get_val("Q_st_loss_kW", units="kW")
        dt = 1.0  # hour

        SOC_init = tech_config["model_inputs"]["performance_parameters"]["SOC_init"]
        S_TES = tech_config["model_inputs"]["performance_parameters"]["S_TES_kWh"]
        E_prev = SOC_init * S_TES
        for t in range(n):
            # E_st(t) = E_st(t-1) + (Q_ch - Q_dis - Q_st_loss) * dt
            expected = E_prev + (Q_ch[t] - Q_dis[t] - Q_st_loss[t]) * dt
            assert E_st[t] == approx(expected, rel=1e-9, abs=1e-6)
            E_prev = E_st[t]

    def test_petes_loss_rates(self, petes_config):
        tech_config, plant_config, n = petes_config
        prob = _create_problem(tech_config, plant_config)

        prob.set_val("electricity_in_kW", np.full(n, 50_000.0))
        prob.set_val("heat_demand_kW", np.full(n, 20_000.0))
        prob.run_model()

        Q_ch = prob.get_val("Q_ch_kW", units="kW")
        Q_dis = prob.get_val("Q_dis_kW", units="kW")
        Q_ch_loss = prob.get_val("Q_ch_loss_kW", units="kW")
        Q_dis_loss = prob.get_val("Q_dis_loss_kW", units="kW")

        eta_ch = tech_config["model_inputs"]["performance_parameters"]["eta_ch"]
        eta_dis = tech_config["model_inputs"]["performance_parameters"]["eta_dis"]

        # Q_ch_loss = Q_ch * (1 - eta_ch) / eta_ch
        assert Q_ch_loss == approx(Q_ch * (1 - eta_ch) / eta_ch, rel=1e-9)
        # Q_dis_loss = Q_dis * (1 - eta_dis)
        assert Q_dis_loss == approx(Q_dis * (1 - eta_dis), rel=1e-9)

    def test_retes_rate_caps(self, retes_config):
        tech_config, plant_config, n = retes_config
        # Start full to test discharge cap
        tech_config["model_inputs"]["performance_parameters"]["SOC_init"] = 1.0
        prob = _create_problem(tech_config, plant_config)

        prob.set_val("electricity_in_kW", np.full(n, 1e9))
        prob.set_val("heat_demand_kW", np.full(n, 1e9))
        prob.run_model()

        Q_ch = prob.get_val("Q_ch_kW", units="kW")
        Q_dis = prob.get_val("Q_dis_kW", units="kW")
        params = tech_config["model_inputs"]["performance_parameters"]
        S_TES = params["S_TES_kWh"]
        # Rates capped at f * S_TES
        assert np.all(Q_ch <= params["f_ch_max"] * S_TES + 1e-6)
        assert np.all(Q_dis <= params["f_dis_max"] * S_TES + 1e-6)

    def test_soc_bounds(self, petes_config):
        tech_config, plant_config, n = petes_config
        tech_config["model_inputs"]["performance_parameters"]["SOC_min"] = 0.1
        tech_config["model_inputs"]["performance_parameters"]["SOC_init"] = 1.0
        prob = _create_problem(tech_config, plant_config)

        prob.set_val("electricity_in_kW", np.full(n, 1e9))
        prob.set_val("heat_demand_kW", np.full(n, 1e9))
        prob.run_model()

        E_st = prob.get_val("E_st_kWh", units="kW*h")
        S_TES = tech_config["model_inputs"]["performance_parameters"]["S_TES_kWh"]
        SOC_min = tech_config["model_inputs"]["performance_parameters"]["SOC_min"]
        assert np.all(E_st >= SOC_min * S_TES - 1e-6)
        assert np.all(E_st <= S_TES + 1e-6)

    def test_invalid_etes_type(self, petes_config):
        tech_config, plant_config, _ = petes_config
        tech_config["model_inputs"]["performance_parameters"]["etes_type"] = "BAD"
        with pytest.raises(ValueError, match="etes_type"):
            _create_problem(tech_config, plant_config)
