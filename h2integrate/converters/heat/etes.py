"""
Electric Thermal Energy Storage (ETES) performance model.

Implements the energy-balance equations from the MILP ETES Optimization
Formulation (Lidor, 2026). Two ETES types are supported:

- "P-ETES": Particle-type ETES with decoupled charging unit (electric heater),
  storage capacity, and discharging unit (e.g., MPBHX). Charging and
  discharging rates are limited by their respective unit power ratings
  (S_ch, S_dis).
- "R-ETES": Refractory-type ETES (e.g., Rondo, Antora) where charging and
  discharging rates are coupled to the storage capacity via rate constants
  f_ch_max and f_dis_max.

The dispatch is implemented as a simple heuristic (not the MILP):
at each timestep, the model attempts to meet the thermal load by discharging
from storage, then uses any available electricity to charge the storage, all
subject to the capacity, rate, and SOC constraints from the formulation.
"""

import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero


def _validate_etes_type(instance, attribute, value):
    valid = ("P-ETES", "R-ETES")
    if value not in valid:
        raise ValueError(f"etes_type must be one of {valid}, got {value!r}")


@define(kw_only=True)
class ETESPerformanceModelConfig(BaseConfig):
    """
    Configuration class for the ETESPerformanceModel.

    Args:
        etes_type (str): ETES type. One of "P-ETES" (decoupled charging,
            storage, and discharging components) or "R-ETES" (integrated
            with rate-coupled charging/discharging).
        S_TES_kWh (float): ETES thermal storage capacity in kWh_th.
        S_ch_kW (float): Charging unit electric power rating in kW_e
            (used for P-ETES only).
        S_dis_kW (float): Discharging unit thermal power rating in kW_th
            (used for P-ETES only).
        eta_ch (float): Charging efficiency (0 < eta_ch <= 1).
        eta_dis (float): Discharging efficiency (0 < eta_dis <= 1).
        f_loss (float): Per-timestep storage loss fraction (fraction of
            stored energy lost each timestep).
        SOC_min (float): Minimum state of charge (fraction of S_TES).
        SOC_init (float): Initial state of charge (fraction of S_TES) at
            the beginning of the simulation. Defaults to 0.5 per the doc.
        f_ch_max (float): Maximum charging rate as a fraction of S_TES per
            hour (used for R-ETES only).
        f_dis_max (float): Maximum discharging rate as a fraction of S_TES
            per hour (used for R-ETES only).
        cost_year (int): Year for cost estimation.
    """

    etes_type: str = field(validator=_validate_etes_type)
    S_TES_kWh: float = field(validator=gt_zero)
    eta_ch: float = field(validator=gt_zero)
    eta_dis: float = field(validator=gt_zero)
    f_loss: float = field(validator=gte_zero)
    SOC_min: float = field(default=0.0, validator=gte_zero)
    SOC_init: float = field(default=0.5, validator=gte_zero)
    S_ch_kW: float = field(default=0.0, validator=gte_zero)
    S_dis_kW: float = field(default=0.0, validator=gte_zero)
    f_ch_max: float = field(default=0.0, validator=gte_zero)
    f_dis_max: float = field(default=0.0, validator=gte_zero)
    cost_year: int = field(validator=gt_zero)


class ETESPerformanceModel(om.ExplicitComponent):
    """
    An OpenMDAO component that simulates ETES dispatch over a time-series
    horizon, given an available electricity profile (for charging) and a
    thermal load profile.

    Inputs (time-series):
        electricity_in_kW: Electricity available for charging the ETES at
            each timestep, in kW_e.
        heat_demand_kW: Thermal load demand at each timestep, in kW_th.

    Outputs (time-series):
        heat_out_kW: Thermal energy delivered to load at each timestep, in
            kW_th.
        unmet_heat_demand_kW: Unmet thermal load at each timestep, in
            kW_th.
        electricity_consumed_kW: Electricity actually consumed for
            charging at each timestep, in kW_e.
        E_st_kWh: Stored thermal energy at each timestep, in kWh_th.
        Q_ch_kW, Q_dis_kW: Charging / discharging rates (thermal), in
            kW_th.
        Q_st_loss_kW, Q_ch_loss_kW, Q_dis_loss_kW: Storage / charging /
            discharging loss rates (thermal), in kW_th.

    Scalar outputs:
        E_total_delivered_kWh: Total thermal energy delivered to load
            over the simulation, in kWh_th.
        round_trip_efficiency: Ratio of total thermal energy delivered to
            total electricity consumed.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = ETESPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        sim = self.options["plant_config"]["plant"]["simulation"]
        self.n_timesteps = int(sim["n_timesteps"])
        self.dt_h = float(sim["dt"]) / 3600.0  # timestep in hours

        # Time-series inputs
        self.add_input(
            "electricity_in_kW",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Electricity available for charging at each timestep",
        )
        self.add_input(
            "heat_demand_kW",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Thermal load demand at each timestep",
        )

        # Time-series outputs
        for name, units, desc in [
            ("heat_out_kW", "kW", "Thermal energy delivered to load"),
            ("unmet_heat_demand_kW", "kW", "Unmet thermal load"),
            ("electricity_consumed_kW", "kW", "Electricity consumed for charging"),
            ("E_st_kWh", "kW*h", "Stored thermal energy at end of each timestep"),
            ("Q_ch_kW", "kW", "Thermal charging rate"),
            ("Q_dis_kW", "kW", "Thermal discharging rate (withdrawn from storage)"),
            ("Q_st_loss_kW", "kW", "Storage loss rate"),
            ("Q_ch_loss_kW", "kW", "Charging loss rate"),
            ("Q_dis_loss_kW", "kW", "Discharging loss rate"),
        ]:
            self.add_output(name, val=0.0, shape=self.n_timesteps, units=units, desc=desc)

        # Scalar outputs
        self.add_output(
            "E_total_delivered_kWh",
            val=0.0,
            units="kW*h",
            desc="Total thermal energy delivered to load over the simulation",
        )
        self.add_output(
            "round_trip_efficiency",
            val=0.0,
            desc="Ratio of thermal energy delivered to electricity consumed",
        )

    def compute(self, inputs, outputs):
        cfg = self.config
        n = self.n_timesteps
        dt = self.dt_h

        S_TES = float(cfg.S_TES_kWh)
        eta_ch = float(cfg.eta_ch)
        eta_dis = float(cfg.eta_dis)
        f_loss = float(cfg.f_loss)
        SOC_min = float(cfg.SOC_min)

        E_min = SOC_min * S_TES
        E_max = S_TES

        # Rate caps (kW_th withdrawn from / added to storage)
        if cfg.etes_type == "P-ETES":
            # P-ETES: decoupled. Charging rate cap = S_ch * eta_ch (thermal added to
            # storage from electric input of S_ch). Discharging rate cap = S_dis /
            # eta_dis (storage withdrawal to deliver S_dis of thermal output).
            ch_rate_cap = float(cfg.S_ch_kW) * eta_ch
            dis_rate_cap = float(cfg.S_dis_kW) / eta_dis if eta_dis > 0 else np.inf
        else:  # R-ETES: integrated, rates coupled to S_TES
            ch_rate_cap = float(cfg.f_ch_max) * S_TES
            dis_rate_cap = float(cfg.f_dis_max) * S_TES

        elec_in = np.asarray(inputs["electricity_in_kW"], dtype=float)
        load = np.asarray(inputs["heat_demand_kW"], dtype=float)

        heat_out = np.zeros(n)
        unmet = np.zeros(n)
        elec_used = np.zeros(n)
        E_st = np.zeros(n)
        Q_ch = np.zeros(n)
        Q_dis = np.zeros(n)
        Q_st_loss = np.zeros(n)
        Q_ch_loss = np.zeros(n)
        Q_dis_loss = np.zeros(n)

        E_prev = float(cfg.SOC_init) * S_TES

        for t in range(n):
            # Storage standing loss (energy lost during this timestep, based on
            # state at start of timestep). Q_st_loss is the rate over Δt.
            loss_energy = E_prev * f_loss
            q_st_loss_rate = loss_energy / dt if dt > 0 else 0.0

            # --- Discharge to meet thermal load ---
            # Required storage-side withdrawal rate to meet load:
            dis_req_rate = load[t] / eta_dis if eta_dis > 0 else 0.0
            # Available energy in storage after standing loss, above SOC_min:
            available_E = max(E_prev - loss_energy - E_min, 0.0)
            dis_available_rate = available_E / dt if dt > 0 else 0.0
            dis_rate = min(dis_req_rate, dis_rate_cap, dis_available_rate)
            heat_delivered = dis_rate * eta_dis

            # --- Charge with available electricity ---
            # Thermal added to storage per electricity input:
            ch_req_rate_thermal = elec_in[t] * eta_ch
            # Headroom in storage after standing loss and discharge:
            headroom_E = max(
                E_max - (E_prev - loss_energy - dis_rate * dt),
                0.0,
            )
            ch_headroom_rate = headroom_E / dt if dt > 0 else 0.0
            ch_rate = min(ch_req_rate_thermal, ch_rate_cap, ch_headroom_rate)
            elec_consumed = ch_rate / eta_ch if eta_ch > 0 else 0.0

            # Update storage state
            E_new = E_prev - loss_energy + (ch_rate - dis_rate) * dt
            # Numerical clamp
            E_new = min(max(E_new, E_min), E_max)

            # Record outputs
            heat_out[t] = heat_delivered
            unmet[t] = max(load[t] - heat_delivered, 0.0)
            elec_used[t] = elec_consumed
            E_st[t] = E_new
            Q_ch[t] = ch_rate
            Q_dis[t] = dis_rate
            Q_st_loss[t] = q_st_loss_rate
            # Loss rates from formulation:
            #   Q_ch_loss = Q_ch * (1 - eta_ch) / eta_ch   (electric-side loss)
            #   Q_dis_loss = Q_dis * (1 - eta_dis)         (thermal-side loss)
            Q_ch_loss[t] = ch_rate * (1.0 - eta_ch) / eta_ch if eta_ch > 0 else 0.0
            Q_dis_loss[t] = dis_rate * (1.0 - eta_dis)

            E_prev = E_new

        outputs["heat_out_kW"] = heat_out
        outputs["unmet_heat_demand_kW"] = unmet
        outputs["electricity_consumed_kW"] = elec_used
        outputs["E_st_kWh"] = E_st
        outputs["Q_ch_kW"] = Q_ch
        outputs["Q_dis_kW"] = Q_dis
        outputs["Q_st_loss_kW"] = Q_st_loss
        outputs["Q_ch_loss_kW"] = Q_ch_loss
        outputs["Q_dis_loss_kW"] = Q_dis_loss

        total_heat = float(np.sum(heat_out) * dt)
        total_elec = float(np.sum(elec_used) * dt)
        outputs["E_total_delivered_kWh"] = total_heat
        outputs["round_trip_efficiency"] = total_heat / total_elec if total_elec > 0 else 0.0
