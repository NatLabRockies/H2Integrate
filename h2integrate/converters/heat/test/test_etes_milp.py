import numpy as np
import pytest
from pytest import approx

from h2integrate.converters.heat.etes_milp import (
    ETESMILPConfig,
    solve_etes_milp,
)


def _peak_price_profile(n=24):
    """Cheap nights, expensive afternoons (peaks 12-20)."""
    price = np.full(n, 0.02)
    price[12:20] = 0.20
    return price


@pytest.mark.unit
class TestETESMILP:
    def test_petes_sizing_basic(self):
        n = 24
        load = np.full(n, 10_000.0)  # 10 MW_th constant
        price = _peak_price_profile(n)
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.0,
            t_ch_min_h=2.0,
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
            fixed_charge_rate=0.10,
            opex_fraction=0.04,
            cyclic=True,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)

        # Sizes must be strictly positive and finite
        assert res.S_TES_kWh > 0
        assert res.S_ch_kW > 0
        assert res.S_dis_kW > 0
        # Total demand over horizon = 10 MW * 24 h = 240 MWh
        total_heat_delivered = float(np.sum(res.Q_dis_kW * cfg.eta_dis))
        assert total_heat_delivered == approx(np.sum(load), rel=1e-4)
        # No unmet load
        assert np.all(res.unmet_load_kW < 1e-6)

    def test_petes_uses_cheap_electricity(self):
        n = 24
        load = np.full(n, 10_000.0)
        price = _peak_price_profile(n)
        # Fix sizes so the optimizer doesn't trade off S_ch cost vs. electricity
        # cost. With ample charging capacity, charging should fully avoid the
        # expensive hours.
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.0,
            t_ch_min_h=2.0,
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
            S_TES_fixed_kWh=500_000.0,
            S_ch_fixed_kW=100_000.0,
            S_dis_fixed_kW=20_000.0,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)

        # Charging should fully avoid the expensive hours (price = 0.20)
        cheap_hours = price < 0.05
        expensive_hours = ~cheap_hours
        ch_in_cheap = float(np.sum(res.Q_ch_kW[cheap_hours]))
        ch_in_expensive = float(np.sum(res.Q_ch_kW[expensive_hours]))
        assert ch_in_expensive < 1e-3
        assert ch_in_cheap > 0

    def test_storage_energy_balance(self):
        n = 24
        load = np.full(n, 8_000.0)
        price = _peak_price_profile(n)
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.01,
            t_ch_min_h=2.0,
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)

        dt = 1.0
        E_prev = cfg.SOC_init * res.S_TES_kWh
        for t in range(n):
            expected = E_prev * (1.0 - cfg.f_loss) + (res.Q_ch_kW[t] - res.Q_dis_kW[t]) * dt
            assert res.E_st_kWh[t] == approx(expected, rel=1e-5, abs=1e-3)
            E_prev = res.E_st_kWh[t]

    def test_cyclic_constraint(self):
        n = 12
        load = np.full(n, 5_000.0)
        price = np.tile([0.02, 0.20], n // 2)
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.0,
            t_ch_min_h=2.0,
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
            cyclic=True,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)
        # Final E_st == initial E_st (= SOC_init * S_TES)
        E0 = cfg.SOC_init * res.S_TES_kWh
        assert res.E_st_kWh[-1] == approx(E0, rel=1e-5, abs=1e-3)

    def test_retes_rate_coupling(self):
        n = 24
        load = np.full(n, 10_000.0)
        price = _peak_price_profile(n)
        cfg = ETESMILPConfig(
            etes_type="R-ETES",
            eta_ch=0.98, eta_dis=0.90, f_loss=0.0068,
            f_ch_max=0.3, f_dis_max=0.2,
            C_lin_TES=10.0, C_min_TES=3.0,
            fixed_charge_rate=0.10,
            opex_fraction=0.04,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)

        # In R-ETES, S_ch and S_dis are not sized (= 0); charging/discharging
        # rates are bounded by f * S_TES.
        assert res.S_ch_kW == approx(0.0, abs=1e-6)
        assert res.S_dis_kW == approx(0.0, abs=1e-6)
        assert np.all(res.Q_ch_kW <= cfg.f_ch_max * res.S_TES_kWh + 1e-4)
        assert np.all(res.Q_dis_kW <= cfg.f_dis_max * res.S_TES_kWh + 1e-4)

    def test_minimum_charging_time(self):
        n = 24
        load = np.full(n, 10_000.0)
        price = _peak_price_profile(n)
        t_min = 6.0
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.0,
            t_ch_min_h=t_min,
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)
        # S_ch * eta_ch * t_ch_min <= S_TES
        assert res.S_ch_kW * cfg.eta_ch * t_min <= res.S_TES_kWh + 1e-3

    def test_dispatch_only_mode(self):
        """Fix sizes and only optimize dispatch."""
        n = 24
        load = np.full(n, 8_000.0)
        price = _peak_price_profile(n)
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.0,
            t_ch_min_h=2.0,
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
            S_TES_fixed_kWh=200_000.0,
            S_ch_fixed_kW=50_000.0,
            S_dis_fixed_kW=20_000.0,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)
        assert res.S_TES_kWh == approx(200_000.0, rel=1e-6)
        assert res.S_ch_kW == approx(50_000.0, rel=1e-6)
        assert res.S_dis_kW == approx(20_000.0, rel=1e-6)
        # Charging unit not exceeded
        assert np.all(res.Q_ch_kW <= res.S_ch_kW * cfg.eta_ch + 1e-4)
        # Discharging unit not exceeded
        assert np.all(res.Q_dis_kW * cfg.eta_dis <= res.S_dis_kW + 1e-4)

    def test_unmet_load_allowed(self):
        """If sizes are too small and unmet allowed, model should drop load
        when penalty < grid cost."""
        n = 24
        load = np.full(n, 100_000.0)  # very large load
        price = np.full(n, 0.50)  # expensive grid
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.0,
            t_ch_min_h=0.0,  # disable to avoid sizing coupling
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
            S_TES_fixed_kWh=1.0,  # essentially no storage
            S_ch_fixed_kW=1.0,
            S_dis_fixed_kW=1.0,
            allow_unmet_load=True,
            unmet_load_penalty=0.10,  # cheaper to shed than charge from grid
            cyclic=False,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)
        # Should have substantial unmet load
        assert np.sum(res.unmet_load_kW) > 0

    def test_cost_breakdown_consistency(self):
        n = 24
        load = np.full(n, 5_000.0)
        price = _peak_price_profile(n)
        cfg = ETESMILPConfig(
            etes_type="P-ETES",
            eta_ch=0.95, eta_dis=0.73, f_loss=0.0,
            t_ch_min_h=2.0,
            C_lin_TES=5.0, C_min_TES=1.5,
            C_lin_ch=100.0, C_lin_dis=150.0,
            fixed_charge_rate=0.10,
            opex_fraction=0.04,
        )
        res = solve_etes_milp(cfg, price, load, dt_h=1.0)

        # Total annualized cost = annualized capex + opex + electricity
        assert res.total_annualized_cost_USD == approx(
            res.annualized_capex_USD + res.annual_opex_USD + res.annual_electricity_cost_USD,
            rel=1e-6,
        )
        # Objective value matches total (no unmet load => no penalty)
        assert res.objective_value == approx(res.total_annualized_cost_USD, rel=1e-6)

    def test_invalid_etes_type_raises(self):
        with pytest.raises(ValueError, match="etes_type"):
            ETESMILPConfig(
                etes_type="BAD",
                eta_ch=0.9, eta_dis=0.7, f_loss=0.0,
            )
