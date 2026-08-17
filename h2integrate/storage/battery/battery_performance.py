"""
# NOTE: ``simses.battery`` must be imported before ``simses.degradation`` to avoid a
# circular import within simses (>=2.1.1): importing ``simses.degradation`` first leaves
# ``simses.degradation.calendar`` partially initialized when ``simses.battery.cell`` pulls
# in ``simses.degradation.degradation``. Importing the battery package first fully loads
# both sub-packages in a safe order. (Plain ``import`` sorts above ``from`` imports.)
"""

import math

import numpy as np
import simses.battery  # noqa: F401  (import-order side effect; see note above)
from attrs import field, define
from openmdao.utils import units as om_units
from simses.degradation import DegradationModel
from simses.battery.state import BatteryState
from simses.battery.battery import Battery
from simses.thermal.ambient import AmbientThermalModel
from simses.degradation.state import DegradationState
from simses.converter.converter import Converter
from simses.model.cell.sony_lfp import SonyLFP
from simses.degradation.cycle_detector import HalfCycle
from simses.model.converter.fix_efficiency import FixedEfficiency
from simses.model.degradation.sony_lfp_cyclic import (
    A_RINC,
    B_RINC,
    C_RINC as CYC_C_RINC,
    D_RINC as CYC_D_RINC,
    A_QLOSS,
    B_QLOSS,
    C_QLOSS as CYC_C_QLOSS,
    D_QLOSS as CYC_D_QLOSS,
    SonyLFPCyclicDegradation,
)
from simses.model.degradation.sony_lfp_calendar import (
    T_REF,
    C_RINC as CAL_C_RINC,
    D_RINC as CAL_D_RINC,
    C_QLOSS as CAL_C_QLOSS,
    D_QLOSS as CAL_D_QLOSS,
    EA_RINC,
    EA_QLOSS,
    K_REF_RINC,
    K_REF_QLOSS,
    R,
    SonyLFPCalendarDegradation,
)

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, range_val, range_val_or_none
from h2integrate.storage.storage_baseclass import (
    StoragePerformanceBase,
    StoragePerformanceBaseConfig,
)


class LFP280Ah(SonyLFP):
    """280 Ah / 3.2 V prismatic LFP cell scaled from the SonyLFP OCV/resistance curves.

    Resistance scaling:
        Step 1 - capacity scaling: R scales as 1/Q, so the first factor is 3/280.
        Step 2 - design correction for large-format prismatic multi-tab cells.
        Combined: _SCALE = 0.003888, matching about 0.18 mOhm at SOC=0.5, T=25 C.
    """

    _SCALE = 0.18e-3 / ((0.044767041 + 0.047827935) / 2)

    def __init__(self):
        super().__init__()
        self.electrical.nominal_capacity = 280.0  # Ah
        # Thermal properties for a large-format prismatic cell (vs. the 70 g 26650 reference).
        # mass=1.5 kg, h=23 W/m²K gives C_th≈6.5 MJ/K, R_th≈1.73 mK/W, τ≈3.1 h
        # → ΔT ≈ 10 °C at end of 2-hour C/2 discharge.
        self.thermal.mass = 3.0  # kg per cell
        self.thermal.convection_coefficient = 23.0  # W/m²K

    def internal_resistance(self, state):
        return super().internal_resistance(state) * self._SCALE


class ScaledLFPCalendarDegradation(SonyLFPCalendarDegradation):
    def __init__(self, deg_scale: float):
        super().__init__()
        self._deg_scale = deg_scale

    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        if dt == 0.0:
            return 0.0
        T_K = state.T + 273.15
        T_REF_K = T_REF + 273.15
        k_T_q = (K_REF_QLOSS * self._deg_scale) * math.exp(
            -EA_QLOSS / R * (1.0 / T_K - 1.0 / T_REF_K)
        )
        k_soc_q = CAL_C_QLOSS * (state.soc - 0.5) ** 3 + CAL_D_QLOSS
        stress_q = k_T_q * k_soc_q
        if stress_q > 0.0:
            virtual_time = (accumulated_qloss / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_time + dt) - accumulated_qloss
        else:
            delta_q = 0.0
        return delta_q

    def update_resistance(self, state: BatteryState, dt: float) -> float:
        if dt == 0.0:
            return 0.0
        T_K = state.T + 273.15
        T_REF_K = T_REF + 273.15
        k_T_r = (K_REF_RINC * self._deg_scale) * math.exp(
            -EA_RINC / R * (1.0 / T_K - 1.0 / T_REF_K)
        )
        k_soc_r = CAL_C_RINC * (state.soc - 0.5) ** 2 + CAL_D_RINC
        return k_T_r * k_soc_r * dt


class ScaledLFPCyclicDegradation(SonyLFPCyclicDegradation):
    def __init__(self, deg_scale: float):
        super().__init__()
        self._deg_scale = deg_scale

    def update_capacity(
        self,
        state: BatteryState,
        half_cycle: HalfCycle,
        accumulated_qloss: float,
    ) -> float:
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0
        k_crate_q = (A_QLOSS * self._deg_scale) * half_cycle.c_rate + (B_QLOSS * self._deg_scale)
        k_dod_q = CYC_C_QLOSS * (half_cycle.depth_of_discharge - 0.6) ** 3 + CYC_D_QLOSS
        stress_q = k_crate_q * k_dod_q
        if stress_q > 0.0:
            virtual_fec = (accumulated_qloss * 100.0 / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_fec + delta_fec) / 100.0 - accumulated_qloss
        else:
            delta_q = 0.0
        return delta_q

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle) -> float:
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0
        k_crate_r = (A_RINC * self._deg_scale) * half_cycle.c_rate + (B_RINC * self._deg_scale)
        k_dod_r = CYC_C_RINC * (half_cycle.depth_of_discharge - 0.5) ** 3 + CYC_D_RINC
        return k_crate_r * k_dod_r * delta_fec / 100.0


@define(kw_only=True)
class BatteryPerformanceModelConfig(StoragePerformanceBaseConfig):
    """Configuration class for storage performance models.

    This class defines configuration parameters for simulating storage
    performance with the Pyomo controllers. It includes
    specifications such as capacity, charge rate, state-of-charge limits,
    and charge/discharge efficiencies.

    Attributes:
        commodity (str): name of commodity
        commodity_rate_units (str): Units of the commodity (e.g., "kg/h").
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
        max_capacity (float):  Maximum storage energy capacity in commodity_amount_units.
            Must be greater than zero.
        max_charge_rate (float): Rated commodity capacity of the storage  in commodity_rate_units.
            Must be greater than zero.
        min_soc_fraction (float): Minimum allowable state of charge as a fraction (0 to 1).
        max_soc_fraction (float): Maximum allowable state of charge as a fraction (0 to 1).
        init_soc_fraction (float): Initial state of charge as a fraction (0 to 1).
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., kW*h or kg). If not provided, defaults to commodity_rate_units*h.
        max_discharge_rate (float | None, optional): Maximum rate at which the commodity can be
            discharged (in units per time step, e.g., "kg/time step"). This rate does not include
            the discharge_efficiency. Only required if `charge_equals_discharge` is False.
        charge_equals_discharge (bool, optional): If True, set the max_discharge_rate equal to the
            max_charge_rate. If False, specify the max_discharge_rate as a value different than
            the max_charge_rate. Defaults to True.
        charge_efficiency (float | None, optional): Efficiency of charging the storage, represented
            as a decimal between 0 and 1 (e.g., 0.9 for 90% efficiency). Optional if
            `round_trip_efficiency` is provided.
        discharge_efficiency (float | None, optional): Efficiency of discharging the storage,
            represented as a decimal between 0 and 1 (e.g., 0.9 for 90% efficiency). Optional if
            `round_trip_efficiency` is provided.
        round_trip_efficiency (float | None, optional): Combined efficiency of charging and
            discharging the storage, represented as a decimal between 0 and 1 (e.g., 0.81 for
            81% efficiency). Optional if `charge_efficiency` and `discharge_efficiency` are
            provided.

    """

    commodity: str = field()
    commodity_rate_units: str = field()

    max_capacity: float = field(validator=gt_zero)
    max_charge_rate: float = field(validator=gt_zero)

    init_soc_fraction: float = field(validator=range_val(0, 1))

    commodity_amount_units: str = field(default=None)
    max_discharge_rate: float | None = field(default=None)
    charge_equals_discharge: bool = field(default=True)

    charge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    discharge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    round_trip_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))

    deg_scale: float = field(default=0.7056, validator=range_val(0, 1))
    eol_soh_capacity: float = field(default=0.8, validator=range_val(0, 1))
    # TODO convert from power and energy ratings (see math in chat)
    series_count: int = field(default=336, converter=int, validator=gt_zero)
    parallel_count: int = field(default=16, converter=int, validator=gt_zero)
    battery_temperature_c: float = field(default=25.0)
    converter_efficiency: float = field(default=0.96, validator=range_val(0, 1))
    converter_max_power: float = field(default=2400.0, validator=gt_zero)

    # TODO degradation: add additional parameters for degradation here
    cop: float = field(validator=gt_zero)

    def __attrs_post_init__(self):
        """
        Post-initialization logic to validate and calculate efficiencies.

        Ensures that either `charge_efficiency` and `discharge_efficiency` are provided,
        or `round_trip_efficiency` is provided. If `round_trip_efficiency` is provided,
        it calculates `charge_efficiency` and `discharge_efficiency` as the square root
        of `round_trip_efficiency`.
        """
        if (self.round_trip_efficiency is not None) and (
            self.charge_efficiency is None and self.discharge_efficiency is None
        ):
            # Calculate charge and discharge efficiencies from round-trip efficiency
            self.charge_efficiency = np.sqrt(self.round_trip_efficiency)
            self.discharge_efficiency = np.sqrt(self.round_trip_efficiency)

        if self.charge_efficiency is None or self.discharge_efficiency is None:
            raise ValueError(
                "Exactly one of the following sets of parameters must be set: (a) "
                "`round_trip_efficiency`, or (b) both `charge_efficiency` "
                "and `discharge_efficiency`."
            )

        if self.charge_equals_discharge:
            if (
                self.max_discharge_rate is not None
                and self.max_discharge_rate != self.max_charge_rate
            ):
                msg = (
                    "Max discharge rate does not equal max charge rate but charge_equals_discharge "
                    f"is True. Discharge rate is {self.max_discharge_rate} and charge rate "
                    f"is {self.max_charge_rate}."
                )
                raise ValueError(msg)

            self.max_discharge_rate = self.max_charge_rate

        if not self.charge_equals_discharge and self.max_discharge_rate is None:
            msg = (
                "max_discharge_rate is required when charge_equals_discharge is False. "
                "Please input the discharge rate using the key `max_discharge_rate`."
            )
            raise ValueError(msg)

        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"


class BatteryPerformanceModel(StoragePerformanceBase):
    """OpenMDAO component for a storage component."""

    _time_step_bounds = (
        60,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        self.config = BatteryPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        self.commodity = self.config.commodity
        self.commodity_rate_units = self.config.commodity_rate_units
        self.commodity_amount_units = self.config.commodity_amount_units

        super().setup()

        self.add_discrete_input(
            "solar_resource_data",
            val={},
            desc="Solar resource data dictionary",
        )

        self.add_output(
            f"{self.commodity}_auxiliary_demand",
            shape=self.n_timesteps,
            desc="Electricity demand for running battery auxiliary systems",
        )

        # Internal SimSES timeseries exposed as OpenMDAO outputs (one per quantity) for
        # downstream diagnostics/plotting.
        self.add_output(
            "voltage", shape=self.n_timesteps, units="V", desc="Battery terminal voltage"
        )
        self.add_output("current", shape=self.n_timesteps, units="A", desc="Battery current")
        self.add_output(
            "temperature", shape=self.n_timesteps, units="degC", desc="Battery temperature"
        )
        self.add_output(
            "battery_loss", shape=self.n_timesteps, units="W", desc="Battery internal loss"
        )
        self.add_output(
            "battery_heat", shape=self.n_timesteps, units="W", desc="Battery heat generation"
        )
        self.add_output(
            "soh_capacity",
            shape=self.n_timesteps,
            units="unitless",
            desc="State of health, capacity (fraction of nominal capacity)",
        )
        self.add_output(
            "soh_resistance",
            shape=self.n_timesteps,
            units="unitless",
            desc="State of health, resistance (multiple of nominal resistance)",
        )
        self.add_output(
            "power_ac",
            shape=self.n_timesteps,
            units="W",
            desc="AC-side power (positive = charge)",
        )
        self.add_output(
            "power_dc",
            shape=self.n_timesteps,
            units="W",
            desc="DC-side power (positive = charge)",
        )
        self.add_output("converter_loss", shape=self.n_timesteps, units="W", desc="Converter loss")

        # TODO degradation: adjustments for degradation

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """Run the storage performance model."""
        self.current_soc = self.config.init_soc_fraction

        inputs["max_charge_rate"][0]
        if "max_discharge_rate" in inputs:
            discharge_rate = inputs["max_discharge_rate"][0]
        else:
            discharge_rate = inputs["max_charge_rate"][0]
        storage_capacity = inputs["storage_capacity"][0]

        # H2I dispatch command: positive = discharge, negative = charge (commodity_rate_units)
        power_profile = inputs[f"{self.commodity}_command_value"]

        # ---------------------------------------------------------------------------
        # Battery pack + inverter (fixed Megapack-style topology, from config)
        # ---------------------------------------------------------------------------
        cell = LFP280Ah()

        # TODO check sizing
        battery = Battery(
            cell=cell,
            circuit=(self.config.series_count, self.config.parallel_count),
            initial_states={
                "start_soc": self.config.init_soc_fraction,
                "start_T": self.config.battery_temperature_c,
            },
            degradation=DegradationModel(
                calendar=ScaledLFPCalendarDegradation(self.config.deg_scale),
                cyclic=ScaledLFPCyclicDegradation(self.config.deg_scale),
                initial_soc=self.config.init_soc_fraction,
                initial_state=DegradationState(qloss_cal=1e-4),
            ),
        )

        converter = Converter(
            loss_model=FixedEfficiency(self.config.converter_efficiency),
            max_power=om_units.convert_units(
                self.config.converter_max_power, self.commodity_rate_units, "W"
            ),
            storage=battery,
        )

        # ---------------------------------------------------------------------------
        # Thermal model: constant ambient, battery registered as thermal node
        # #TODO check battery temp ambient
        # ---------------------------------------------------------------------------
        thermal = AmbientThermalModel(
            T_ambient=self.config.battery_temperature_c, components=[battery]
        )

        # ---------------------------------------------------------------------------
        # Simulation loop
        # ---------------------------------------------------------------------------
        keys = ["soc", "v", "i", "T", "loss", "heat", "soh_Q", "soh_R"]
        log = {k: np.empty(self.n_timesteps) for k in keys}
        power_ac = np.empty(self.n_timesteps)
        power_dc = np.empty(self.n_timesteps)
        conv_loss = np.empty(self.n_timesteps)

        for i, p in enumerate(power_profile):
            # H2I sign (+discharge) -> SimSES AC sign (+charge)
            converter.step(
                -om_units.convert_units(float(p), self.commodity_rate_units, "W"), self.dt
            )
            thermal.step(self.dt)  # update battery temperature after each step
            for k in keys:
                log[k][i] = getattr(battery.state, k)
            power_ac[i] = converter.state.power  # AC power (W), positive = charge
            power_dc[i] = battery.state.power  # AC power (W), positive = charge
            conv_loss[i] = converter.state.loss

        #############

        # Populate all OpenMDAO outputs defined in this class and its parent classes.
        # Convert SimSES AC power (W, +charge) back to H2I convention
        # (commodity_rate_units, +discharge).
        power_ts = -om_units.convert_units(power_ac, "W", self.commodity_rate_units)

        # --- BatteryPerformanceModel outputs ---
        # TODO calc aux power
        outputs[f"{self.commodity}_auxiliary_demand"] = np.zeros(self.n_timesteps)
        outputs["voltage"] = log["v"]
        outputs["current"] = log["i"]
        outputs["temperature"] = log["T"]
        outputs["battery_loss"] = log["loss"]
        outputs["battery_heat"] = log["heat"]
        outputs["soh_capacity"] = log["soh_Q"]
        outputs["soh_resistance"] = log["soh_R"]
        outputs["power_ac"] = power_ac
        outputs["power_dc"] = power_dc
        outputs["converter_loss"] = conv_loss

        # --- StoragePerformanceBase outputs ---
        outputs["storage_duration"] = (
            storage_capacity / discharge_rate if discharge_rate > 0 else 0.0
        )
        outputs["SOC"] = log["soc"] * 100.0  # fraction -> percent
        outputs[f"storage_{self.commodity}_charge"] = np.where(power_ts < 0, power_ts, 0.0)
        outputs[f"storage_{self.commodity}_discharge"] = np.where(power_ts > 0, power_ts, 0.0)

        # --- PerformanceModelBaseClass outputs ---
        outputs[f"{self.commodity}_out"] = power_ts
        outputs[f"rated_{self.commodity}_production"] = discharge_rate
        outputs[f"total_{self.commodity}_produced"] = np.sum(power_ts) * self.dt_amount
        outputs[f"annual_{self.commodity}_produced"] = outputs[
            f"total_{self.commodity}_produced"
        ] * (1 / self.fraction_of_year_simulated)
        outputs["replacement_schedule"] = np.zeros(self.plant_life)
        outputs["operational_life"] = self.plant_life

        if discharge_rate <= 0:
            outputs["capacity_factor"] = 0.0
            outputs["standard_capacity_factor"] = 0.0
        else:
            # Gross discharge timeseries (commodity_rate_units, discharge only).
            discharge_ts = outputs[f"storage_{self.commodity}_discharge"]
            total_commodity_discharged = discharge_ts.sum() * self.dt_amount

            # Scalar average discharge capacity factor over the whole simulation.
            outputs["standard_capacity_factor"] = total_commodity_discharged / (
                discharge_rate * self.n_timesteps * self.dt_amount
            )

            # Per-year discharge capacity factor and year-end capacity state-of-health over
            # the simulated horizon. The simulation may span whole years plus an optional
            # partial trailing year; each simulated year gets its own capacity factor and
            # end-of-year SOH.
            steps_per_year = round(31_536_000 / self.dt)  # timesteps in one year
            n_sim_years = math.ceil(self.n_timesteps / steps_per_year)
            soh_capacity_ts = log["soh_Q"]
            sim_cf = np.zeros(n_sim_years)
            sim_soh_year_end = np.zeros(n_sim_years)
            for year in range(n_sim_years):
                start = year * steps_per_year
                end = min(start + steps_per_year, self.n_timesteps)
                segment_hours = (end - start) * self.dt_amount
                sim_cf[year] = (discharge_ts[start:end].sum() * self.dt_amount) / (
                    discharge_rate * segment_hours
                )
                sim_soh_year_end[year] = soh_capacity_ts[end - 1]

            # Annual capacity-SOH degradation rate used to project SOH beyond the simulated
            # horizon (i.e. once the simulated years are exhausted before the battery hits
            # end-of-life):
            #   - Less than one year simulated: extrapolate the average degradation over the
            #     whole simulation to a per-year rate.
            #   - One year or more simulated: use the degradation over the last full
            #     simulated year.
            years_simulated = self.n_timesteps / steps_per_year
            soh_start = soh_capacity_ts[0]
            if years_simulated < 1.0:
                annual_deg_rate = (soh_start - sim_soh_year_end[-1]) / years_simulated
            else:
                n_full_years = int(self.n_timesteps // steps_per_year)
                idx_after = n_full_years * steps_per_year - 1
                idx_before = (n_full_years - 1) * steps_per_year - 1
                soh_before = soh_capacity_ts[idx_before] if idx_before >= 0 else soh_start
                annual_deg_rate = soh_before - soh_capacity_ts[idx_after]
            annual_deg_rate = max(float(annual_deg_rate), 0.0)

            # Build one battery-life cycle of per-year year-end SOH and capacity factor,
            # long enough to cover the whole plant life. Within the simulated years the
            # actual per-year values are used. Beyond the simulated horizon the SOH keeps
            # degrading at annual_deg_rate and the capacity factor is scaled down in
            # proportion to the declining SOH (relative to the last simulated year), so the
            # capacity factor tracks degradation rather than being held constant.
            if years_simulated < 1.0:
                # A sub-year simulation never completes a full year, so project every year
                # from the start-of-life SOH at the extrapolated annual rate.
                cycle_soh_end = soh_start - annual_deg_rate * (np.arange(self.plant_life) + 1)
            else:
                cycle_soh_end = np.array(
                    [
                        sim_soh_year_end[y]
                        if y < n_sim_years
                        else sim_soh_year_end[-1] - annual_deg_rate * (y - (n_sim_years - 1))
                        for y in range(self.plant_life)
                    ]
                )

            soh_ref = sim_soh_year_end[-1]
            cycle_cf = np.array(
                [
                    sim_cf[y]
                    if y < n_sim_years
                    else sim_cf[-1] * max(cycle_soh_end[y], 0.0) / soh_ref
                    for y in range(self.plant_life)
                ]
            )

            # Walk the plant life. When the projected year-end SOH reaches the user-specified
            # end-of-life threshold, the battery is replaced (fresh unit) at the start of the
            # following year and the degradation / capacity-factor cycle restarts.
            eol_soh = self.config.eol_soh_capacity
            cf_per_year = np.zeros(self.plant_life)
            replacement_schedule = np.zeros(self.plant_life)
            cycle_year = 0
            for plant_year in range(self.plant_life):
                cf_per_year[plant_year] = cycle_cf[cycle_year]
                if cycle_soh_end[cycle_year] <= eol_soh:
                    if plant_year + 1 < self.plant_life:
                        replacement_schedule[plant_year + 1] = 1.0
                    cycle_year = 0
                else:
                    cycle_year += 1
            outputs["capacity_factor"] = cf_per_year
            outputs["replacement_schedule"] = replacement_schedule
