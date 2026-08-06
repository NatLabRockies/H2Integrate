"""
MILP optimizer for the Electric Thermal Energy Storage (ETES).

Implements the optimization formulation from the MILP ETES Optimization
Formulation (Lidor, 2026). Given a time series of electricity prices and
thermal loads, this module solves for the optimal ETES sizing and dispatch
that minimizes the total annualized cost (annualized CapEx + OpEx + grid
electricity cost).

Two sizing modes are supported via ``etes_type``:

- "P-ETES": separate charging unit (S_ch), storage capacity (S_TES), and
  discharging unit (S_dis) are all sized independently.
- "R-ETES": only the storage capacity (S_TES) is sized; the charging and
  discharging rates are coupled to S_TES via rate constants f_ch_max and
  f_dis_max.

The model is technically a linear program as written in the doc (no
binary variables are required). Mutual-exclusion of charge/discharge can
optionally be enforced with binaries, making the problem a true MILP.

Example
-------
>>> from h2integrate.converters.heat.etes_milp import ETESMILPConfig, solve_etes_milp
>>> import numpy as np
>>> n = 24
>>> cfg = ETESMILPConfig(
...     etes_type="P-ETES",
...     eta_ch=0.95,
...     eta_dis=0.73,
...     f_loss=0.0068,
...     t_ch_min_h=4.0,
...     C_lin_TES=5.0,
...     C_min_TES=1.5,
...     C_lin_ch=100.0,
...     C_lin_dis=150.0,
...     fixed_charge_rate=0.10,
... )
>>> price = np.array([0.02] * 8 + [0.10] * 8 + [0.05] * 8)  # $/kWh_e
>>> load = np.full(24, 10_000.0)  # kW_th
>>> result = solve_etes_milp(cfg, price, load, dt_h=1.0)
>>> result.S_TES_kWh  # doctest: +SKIP
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyomo.environ as pyo
from attrs import field as attrs_field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import gt_zero, gte_zero


_PREFERRED_SOLVERS = ("appsi_highs", "highs", "cbc", "glpk")


def _validate_etes_type(instance, attribute, value):
    valid = ("P-ETES", "R-ETES")
    if value not in valid:
        raise ValueError(f"etes_type must be one of {valid}, got {value!r}")


@define(kw_only=True)
class ETESMILPConfig(BaseConfig):
    """
    Configuration for the ETES MILP optimizer.

    Physical parameters:
        etes_type (str): "P-ETES" or "R-ETES".
        eta_ch (float): Charging efficiency.
        eta_dis (float): Discharging efficiency.
        f_loss (float): Per-timestep storage loss fraction.
        SOC_min (float): Minimum state of charge (fraction of S_TES).
        SOC_init (float): Initial state of charge (fraction of S_TES).
            Defaults to 0.5 per the doc.
        # TODO: Don't think we want the cyclic behavior below
        cyclic (bool): If True, force E_st at end of horizon equal to the
            initial state (typical for annual operation). Defaults to True.
        t_ch_min_h (float): Minimum time (h) for fully charging the
            P-ETES; constrains S_ch <= S_TES / (eta_ch * t_ch_min_h).
            P-ETES only.
        f_ch_max (float): Max charging rate as fraction of S_TES (1/h).
            R-ETES only.
        f_dis_max (float): Max discharging rate as fraction of S_TES
            (1/h). R-ETES only.

    Sizing bounds (optional):
        S_TES_min_kWh, S_TES_max_kWh: bounds on storage capacity.
        S_ch_min_kW, S_ch_max_kW: bounds on charging unit (P-ETES).
        S_dis_min_kW, S_dis_max_kW: bounds on discharging unit (P-ETES).
        S_TES_fixed_kWh, S_ch_fixed_kW, S_dis_fixed_kW: if set (non-None),
            the corresponding size is fixed (dispatch-only mode).

    Cost parameters (linearized):
        C_lin_TES (float): Storage linear cost ($/kWh_th).
        C_const_TES (float): Storage constant cost term ($).
        C_min_TES (float): Minimum allowed cost per kWh_th ($/kWh_th).
        C_lin_ch (float): Charging unit linear cost ($/kW_e). P-ETES.
        C_const_ch (float): Charging unit constant cost ($). P-ETES.
        C_lin_dis (float): Discharging unit linear cost ($/kW_th). P-ETES.
        C_const_dis (float): Discharging unit constant cost ($). P-ETES.

    Annualization:
        fixed_charge_rate (float): Annual fixed charges per dollar of
            CapEx. Defaults to 0.10.
        opex_fraction (float): Annual OpEx as fraction of CapEx. Defaults
            to 0.04.

    Solver options:
        allow_unmet_load (bool): If True, allow load to be partially met
            with a penalty cost. Defaults to False.
        unmet_load_penalty (float): Penalty cost per kWh_th of unmet load
            ($/kWh_th). Only used if allow_unmet_load is True.
        enforce_mutex_charge_dis (bool): If True, add binary variables so
            charging and discharging cannot occur simultaneously (true
            MILP). Defaults to False.
        solver (str | None): Pyomo solver name. If None, the first
            available solver from {appsi_highs, highs, cbc, glpk} is used.
        solver_options (dict | None): Options passed to the solver.
    """

    etes_type: str = attrs_field(validator=_validate_etes_type)
    eta_ch: float = attrs_field(validator=gt_zero)
    eta_dis: float = attrs_field(validator=gt_zero)
    f_loss: float = attrs_field(validator=gte_zero)
    SOC_min: float = attrs_field(default=0.0, validator=gte_zero)
    SOC_init: float = attrs_field(default=0.5, validator=gte_zero)
    cyclic: bool = attrs_field(default=True)

    t_ch_min_h: float = attrs_field(default=0.0, validator=gte_zero)
    f_ch_max: float = attrs_field(default=0.0, validator=gte_zero)
    f_dis_max: float = attrs_field(default=0.0, validator=gte_zero)

    S_TES_min_kWh: float = attrs_field(default=0.0, validator=gte_zero)
    S_TES_max_kWh: float = attrs_field(default=1.0e12, validator=gt_zero)
    S_ch_min_kW: float = attrs_field(default=0.0, validator=gte_zero)
    S_ch_max_kW: float = attrs_field(default=1.0e9, validator=gt_zero)
    S_dis_min_kW: float = attrs_field(default=0.0, validator=gte_zero)
    S_dis_max_kW: float = attrs_field(default=1.0e9, validator=gt_zero)
    S_TES_fixed_kWh: float | None = attrs_field(default=None)
    S_ch_fixed_kW: float | None = attrs_field(default=None)
    S_dis_fixed_kW: float | None = attrs_field(default=None)

    C_lin_TES: float = attrs_field(default=0.0, validator=gte_zero)
    C_const_TES: float = attrs_field(default=0.0, validator=gte_zero)
    C_min_TES: float = attrs_field(default=0.0, validator=gte_zero)
    C_lin_ch: float = attrs_field(default=0.0, validator=gte_zero)
    C_const_ch: float = attrs_field(default=0.0, validator=gte_zero)
    C_lin_dis: float = attrs_field(default=0.0, validator=gte_zero)
    C_const_dis: float = attrs_field(default=0.0, validator=gte_zero)

    fixed_charge_rate: float = attrs_field(default=0.10, validator=gte_zero)
    opex_fraction: float = attrs_field(default=0.04, validator=gte_zero)

    allow_unmet_load: bool = attrs_field(default=False)
    unmet_load_penalty: float = attrs_field(default=1.0e4)
    enforce_mutex_charge_dis: bool = attrs_field(default=False)
    solver: str | None = attrs_field(default=None)
    solver_options: dict | None = attrs_field(default=None)


@dataclass
class ETESMILPResult:
    """Result returned by :func:`solve_etes_milp`."""

    # Optimal sizes
    S_TES_kWh: float
    S_ch_kW: float
    S_dis_kW: float
    # Time series (length n_timesteps)
    E_st_kWh: np.ndarray
    Q_ch_kW: np.ndarray
    Q_dis_kW: np.ndarray
    Q_st_loss_kW: np.ndarray
    Q_ch_loss_kW: np.ndarray
    Q_dis_loss_kW: np.ndarray
    P_grid_kW: np.ndarray
    unmet_load_kW: np.ndarray
    # Cost breakdown
    capex_USD: float
    annual_opex_USD: float
    annual_electricity_cost_USD: float
    annualized_capex_USD: float
    total_annualized_cost_USD: float
    # Diagnostics
    solver_status: str
    termination_condition: str
    objective_value: float


def _pick_solver(name: str | None):
    if name is not None:
        solver = pyo.SolverFactory(name)
        if not solver.available(exception_flag=False):
            raise RuntimeError(f"Requested solver {name!r} is not available.")
        return solver, name
    for s in _PREFERRED_SOLVERS:
        try:
            solver = pyo.SolverFactory(s)
            if solver.available(exception_flag=False):
                return solver, s
        except (ValueError, AttributeError):
            continue
    raise RuntimeError(
        f"No LP/MILP solver available; tried {_PREFERRED_SOLVERS}. "
        "Install one (e.g. `pip install highspy` for HiGHS)."
    )


def solve_etes_milp(
    config: ETESMILPConfig,
    electricity_price: np.ndarray,
    heat_load_kW: np.ndarray,
    dt_h: float = 1.0,
) -> ETESMILPResult:
    """
    Solve the MILP ETES sizing-and-dispatch problem.

    Args:
        config: :class:`ETESMILPConfig` with physical, cost, and solver
            parameters.
        electricity_price: Array of length ``n`` with grid electricity
            prices in $/kWh_e for each timestep.
        heat_load_kW: Array of length ``n`` with thermal load demand in
            kW_th for each timestep.
        dt_h: Timestep length in hours. Defaults to 1.0.

    Returns:
        :class:`ETESMILPResult` containing optimal sizes, dispatch
        time-series, and cost breakdown.
    """
    price = np.asarray(electricity_price, dtype=float)
    load = np.asarray(heat_load_kW, dtype=float)
    if price.shape != load.shape or price.ndim != 1:
        raise ValueError(
            f"electricity_price and heat_load_kW must be 1-D arrays of the "
            f"same length; got {price.shape} and {load.shape}."
        )
    n = len(load)
    T = range(n)

    cfg = config

    m = pyo.ConcreteModel()
    m.T = pyo.Set(initialize=list(T), ordered=True)

    # --- Sizing variables ---
    m.S_TES = pyo.Var(
        domain=pyo.NonNegativeReals,
        bounds=(cfg.S_TES_min_kWh, cfg.S_TES_max_kWh),
        initialize=cfg.S_TES_fixed_kWh
        if cfg.S_TES_fixed_kWh is not None
        else 0.5 * (cfg.S_TES_min_kWh + cfg.S_TES_max_kWh),
    )
    if cfg.S_TES_fixed_kWh is not None:
        m.S_TES.fix(cfg.S_TES_fixed_kWh)

    if cfg.etes_type == "P-ETES":
        m.S_ch = pyo.Var(
            domain=pyo.NonNegativeReals,
            bounds=(cfg.S_ch_min_kW, cfg.S_ch_max_kW),
            initialize=cfg.S_ch_fixed_kW
            if cfg.S_ch_fixed_kW is not None
            else 0.5 * (cfg.S_ch_min_kW + cfg.S_ch_max_kW),
        )
        if cfg.S_ch_fixed_kW is not None:
            m.S_ch.fix(cfg.S_ch_fixed_kW)
        m.S_dis = pyo.Var(
            domain=pyo.NonNegativeReals,
            bounds=(cfg.S_dis_min_kW, cfg.S_dis_max_kW),
            initialize=cfg.S_dis_fixed_kW
            if cfg.S_dis_fixed_kW is not None
            else 0.5 * (cfg.S_dis_min_kW + cfg.S_dis_max_kW),
        )
        if cfg.S_dis_fixed_kW is not None:
            m.S_dis.fix(cfg.S_dis_fixed_kW)
    else:
        # R-ETES: S_ch and S_dis are not sized; fix to zero (cost = 0)
        m.S_ch = pyo.Var(domain=pyo.NonNegativeReals, initialize=0.0)
        m.S_ch.fix(0.0)
        m.S_dis = pyo.Var(domain=pyo.NonNegativeReals, initialize=0.0)
        m.S_dis.fix(0.0)

    # --- Dispatch variables ---
    m.E_st = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.Q_ch = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.Q_dis = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.unmet = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    if not cfg.allow_unmet_load:
        for t in m.T:
            m.unmet[t].fix(0.0)

    # Optional binary on/off vars for mutual exclusion
    if cfg.enforce_mutex_charge_dis:
        m.z_ch = pyo.Var(m.T, domain=pyo.Binary)
        m.z_dis = pyo.Var(m.T, domain=pyo.Binary)
        # Big-M based on storage capacity / rate caps
        bigM = max(cfg.S_TES_max_kWh / max(dt_h, 1e-9), cfg.S_ch_max_kW, cfg.S_dis_max_kW)

        def _ch_on_rule(mm, t):
            return mm.Q_ch[t] <= bigM * mm.z_ch[t]

        def _dis_on_rule(mm, t):
            return mm.Q_dis[t] <= bigM * mm.z_dis[t]

        def _mutex_rule(mm, t):
            return mm.z_ch[t] + mm.z_dis[t] <= 1

        m.ch_on = pyo.Constraint(m.T, rule=_ch_on_rule)
        m.dis_on = pyo.Constraint(m.T, rule=_dis_on_rule)
        m.mutex = pyo.Constraint(m.T, rule=_mutex_rule)

    # --- Storage energy balance ---
    E0 = cfg.SOC_init  # multiplied by S_TES below
    f_loss = cfg.f_loss

    def _balance_rule(mm, t):
        # Storage loss energy over the timestep = E_prev * f_loss
        # E_st[t] = E_prev*(1 - f_loss) + (Q_ch - Q_dis)*dt
        if t == 0:
            E_prev = E0 * mm.S_TES
        else:
            E_prev = mm.E_st[t - 1]
        return mm.E_st[t] == E_prev * (1.0 - f_loss) + (mm.Q_ch[t] - mm.Q_dis[t]) * dt_h

    m.balance = pyo.Constraint(m.T, rule=_balance_rule)

    # SOC bounds
    def _soc_min_rule(mm, t):
        return mm.E_st[t] >= cfg.SOC_min * mm.S_TES

    def _soc_max_rule(mm, t):
        return mm.E_st[t] <= mm.S_TES

    m.soc_min = pyo.Constraint(m.T, rule=_soc_min_rule)
    m.soc_max = pyo.Constraint(m.T, rule=_soc_max_rule)

    # Cyclic boundary
    if cfg.cyclic:
        m.cyclic_con = pyo.Constraint(expr=m.E_st[n - 1] == E0 * m.S_TES)

    # Load-meeting constraint: Q_dis * eta_dis + unmet = load
    def _load_rule(mm, t):
        return mm.Q_dis[t] * cfg.eta_dis + mm.unmet[t] == load[t]

    m.load_con = pyo.Constraint(m.T, rule=_load_rule)

    # Rate / sizing limits per ETES type
    if cfg.etes_type == "P-ETES":
        # Q_ch <= S_ch * eta_ch (charging unit cap; Q_ch is thermal added)
        def _ch_cap_rule(mm, t):
            return mm.Q_ch[t] <= mm.S_ch * cfg.eta_ch

        # Q_dis <= S_dis / eta_dis (discharging unit cap; thermal output S_dis)
        def _dis_cap_rule(mm, t):
            return mm.Q_dis[t] * cfg.eta_dis <= mm.S_dis

        m.ch_cap = pyo.Constraint(m.T, rule=_ch_cap_rule)
        m.dis_cap = pyo.Constraint(m.T, rule=_dis_cap_rule)

        # Minimum charging time: S_ch * eta_ch <= S_TES / t_ch_min
        if cfg.t_ch_min_h > 0:
            m.t_ch_min_con = pyo.Constraint(expr=m.S_ch * cfg.eta_ch * cfg.t_ch_min_h <= m.S_TES)
    else:  # R-ETES: rates coupled to S_TES

        def _ch_cap_rule(mm, t):
            return mm.Q_ch[t] <= cfg.f_ch_max * mm.S_TES

        def _dis_cap_rule(mm, t):
            return mm.Q_dis[t] <= cfg.f_dis_max * mm.S_TES

        m.ch_cap = pyo.Constraint(m.T, rule=_ch_cap_rule)
        m.dis_cap = pyo.Constraint(m.T, rule=_dis_cap_rule)

    # --- Cost variables ---
    # Storage cost: c_tes >= linear; c_tes >= floor (handles economy-of-scale floor)
    m.c_tes = pyo.Var(domain=pyo.NonNegativeReals)
    m.c_tes_lin = pyo.Constraint(expr=m.c_tes >= cfg.C_lin_TES * m.S_TES + cfg.C_const_TES)
    if cfg.C_min_TES > 0:
        m.c_tes_floor = pyo.Constraint(expr=m.c_tes >= cfg.C_min_TES * m.S_TES)

    # Charging / discharging unit costs (P-ETES only; zero for R-ETES since S_ch=S_dis=0)
    m.c_ch = pyo.Var(domain=pyo.NonNegativeReals)
    m.c_dis = pyo.Var(domain=pyo.NonNegativeReals)
    if cfg.etes_type == "P-ETES":
        m.c_ch_lin = pyo.Constraint(expr=m.c_ch >= cfg.C_lin_ch * m.S_ch + cfg.C_const_ch)
        m.c_dis_lin = pyo.Constraint(expr=m.c_dis >= cfg.C_lin_dis * m.S_dis + cfg.C_const_dis)
    else:
        m.c_ch.fix(0.0)
        m.c_dis.fix(0.0)

    # --- Objective: total annualized cost ---
    # CapEx = c_tes + c_ch + c_dis
    # Annualized capex = (FCR + opex_fraction) * CapEx
    # Electricity cost = sum_t (Q_ch[t] / eta_ch) * price[t] * dt
    annualization = cfg.fixed_charge_rate + cfg.opex_fraction
    grid_cost = sum((m.Q_ch[t] / cfg.eta_ch) * float(price[t]) * dt_h for t in m.T)
    unmet_penalty = sum(m.unmet[t] * cfg.unmet_load_penalty * dt_h for t in m.T)

    m.obj = pyo.Objective(
        expr=annualization * (m.c_tes + m.c_ch + m.c_dis) + grid_cost + unmet_penalty,
        sense=pyo.minimize,
    )

    # --- Solve ---
    solver, solver_name = _pick_solver(cfg.solver)
    if cfg.solver_options:
        for k, v in cfg.solver_options.items():
            solver.options[k] = v
    results = solver.solve(m, tee=False)
    status = str(results.solver.status)
    term = str(results.solver.termination_condition)
    if term.lower() not in ("optimal", "feasible", "globally_optimal", "locallyoptimal"):
        raise RuntimeError(
            f"Solver {solver_name!r} did not find an optimal solution: "
            f"status={status}, termination={term}"
        )

    # --- Extract results ---
    S_TES = float(pyo.value(m.S_TES))
    S_ch = float(pyo.value(m.S_ch))
    S_dis = float(pyo.value(m.S_dis))

    E_st = np.array([pyo.value(m.E_st[t]) for t in T])
    Q_ch = np.array([pyo.value(m.Q_ch[t]) for t in T])
    Q_dis = np.array([pyo.value(m.Q_dis[t]) for t in T])
    unmet = np.array([pyo.value(m.unmet[t]) for t in T])

    # Reconstruct loss series consistent with the formulation
    E_prev_series = np.empty(n)
    E_prev_series[0] = cfg.SOC_init * S_TES
    E_prev_series[1:] = E_st[:-1]
    Q_st_loss = E_prev_series * cfg.f_loss / dt_h if dt_h > 0 else np.zeros(n)
    Q_ch_loss = Q_ch * (1.0 - cfg.eta_ch) / cfg.eta_ch if cfg.eta_ch > 0 else np.zeros(n)
    Q_dis_loss = Q_dis * (1.0 - cfg.eta_dis)
    P_grid = Q_ch / cfg.eta_ch if cfg.eta_ch > 0 else np.zeros(n)

    capex = float(pyo.value(m.c_tes + m.c_ch + m.c_dis))
    annual_opex = cfg.opex_fraction * capex
    annualized_capex = cfg.fixed_charge_rate * capex
    annual_electricity_cost = float(np.sum(P_grid * price * dt_h))
    total = annualized_capex + annual_opex + annual_electricity_cost

    return ETESMILPResult(
        S_TES_kWh=S_TES,
        S_ch_kW=S_ch,
        S_dis_kW=S_dis,
        E_st_kWh=E_st,
        Q_ch_kW=Q_ch,
        Q_dis_kW=Q_dis,
        Q_st_loss_kW=Q_st_loss,
        Q_ch_loss_kW=Q_ch_loss,
        Q_dis_loss_kW=Q_dis_loss,
        P_grid_kW=P_grid,
        unmet_load_kW=unmet,
        capex_USD=capex,
        annual_opex_USD=annual_opex,
        annual_electricity_cost_USD=annual_electricity_cost,
        annualized_capex_USD=annualized_capex,
        total_annualized_cost_USD=total,
        solver_status=status,
        termination_condition=term,
        objective_value=float(pyo.value(m.obj)),
    )
