import math

import numpy as np
import pandas as pd
from attrs import field, define
from openmdao.utils import units as om_units
from simses.degradation import DegradationModel
from simses.battery.state import BatteryState
from simses.battery.battery import Battery
from simses.thermal.ambient import AmbientThermalModel
from simses.degradation.state import DegradationState
from simses.model.cell.sony_lfp import SonyLFP
from simses.degradation.cycle_detector import HalfCycle
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
    """280 Ah / 3.2 V prismatic LFP cell scaled from the SonyLFP OCV/resistance curves."""

    _SCALE = 3.0 / 280.0  # resistance scales inversely with capacity

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
    def update_capacity(
        self, state: BatteryState, dt: float, accumulated_qloss: float, _DEG_SCALE
    ) -> float:
        if dt == 0.0:
            return 0.0
        T_K = state.T + 273.15
        T_REF_K = T_REF + 273.15
        k_T_q = (K_REF_QLOSS * _DEG_SCALE) * math.exp(-EA_QLOSS / R * (1.0 / T_K - 1.0 / T_REF_K))
        k_soc_q = CAL_C_QLOSS * (state.soc - 0.5) ** 3 + CAL_D_QLOSS
        stress_q = k_T_q * k_soc_q
        if stress_q > 0.0:
            virtual_time = (accumulated_qloss / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_time + dt) - accumulated_qloss
        else:
            delta_q = 0.0
        return delta_q

    def update_resistance(self, state: BatteryState, dt: float, _DEG_SCALE) -> float:
        if dt == 0.0:
            return 0.0
        T_K = state.T + 273.15
        T_REF_K = T_REF + 273.15
        k_T_r = (K_REF_RINC * _DEG_SCALE) * math.exp(-EA_RINC / R * (1.0 / T_K - 1.0 / T_REF_K))
        k_soc_r = CAL_C_RINC * (state.soc - 0.5) ** 2 + CAL_D_RINC
        return k_T_r * k_soc_r * dt


class ScaledLFPCyclicDegradation(SonyLFPCyclicDegradation):
    def update_capacity(
        self,
        state: BatteryState,
        half_cycle: HalfCycle,
        accumulated_qloss: float,
        _DEG_SCALE: float,
    ) -> float:
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0
        k_crate_q = (A_QLOSS * _DEG_SCALE) * half_cycle.c_rate + (B_QLOSS * _DEG_SCALE)
        k_dod_q = CYC_C_QLOSS * (half_cycle.depth_of_discharge - 0.6) ** 3 + CYC_D_QLOSS
        stress_q = k_crate_q * k_dod_q
        if stress_q > 0.0:
            virtual_fec = (accumulated_qloss * 100.0 / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_fec + delta_fec) / 100.0 - accumulated_qloss
        else:
            delta_q = 0.0
        return delta_q

    def update_resistance(
        self, state: BatteryState, half_cycle: HalfCycle, _DEG_SCALE: float
    ) -> float:
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0
        k_crate_r = (A_RINC * _DEG_SCALE) * half_cycle.c_rate + (B_RINC * _DEG_SCALE)
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

    _DEG_SCALE: float = field(default=0.4, validator=range_val(0, 1))

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
        1,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = BatteryPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        self.commodity = self.config.commodity
        self.commodity_rate_units = self.config.commodity_rate_units
        self.commodity_amount_units = self.config.commodity_amount_units

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

        # TODO degradation: adjustments for degradation

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """Run the storage performance model."""
        self.current_soc = self.config.init_soc_fraction

        inputs["max_charge_rate"][0]
        if "max_discharge_rate" in inputs:
            discharge_rate = inputs["max_discharge_rate"][0]
        else:
            discharge_rate = inputs["max_charge_rate"][0]
        storage_capacity = inputs["storage_capacity"][0]

        power_profile = inputs[f"{self.commodity}_command_value"]
        ### from Ankit

        # ---------------------------------------------------------------------------
        # Battery pack: 239s x 18p  ->  764.8 V * 5040 Ah  ~  3855 kWh
        # ---------------------------------------------------------------------------
        cell = LFP280Ah()

        battery = Battery(
            cell=cell,
            circuit=(239, 18),  # TODO update to be based on provided battery power and energy
            initial_states={
                "start_soc": self.config.init_soc_fraction,
                "start_T": 25.0,
            },  # TODO should be user inputs
            degradation=DegradationModel(
                calendar=ScaledLFPCalendarDegradation(),
                cyclic=ScaledLFPCyclicDegradation(),
                initial_soc=self.config.init_soc_fraction,
                initial_state=DegradationState(qloss_cal=1e-4),
            ),
        )

        summary = pd.Series(
            {
                "nominal_capacity [Ah]": battery.nominal_capacity,
                "nominal_voltage [V]": battery.nominal_voltage,
                "nominal_energy [kWh]": battery.nominal_energy_capacity / 1e3,
                "max_charge_current [A]": battery.max_charge_current,
                "max_discharge_current [A]": battery.max_discharge_current,
                "thermal_capacity [kJ/K]": battery.thermal_capacity / 1e3,
            }
        )
        print("Battery summary:")
        print(summary.to_string())
        print()

        # ---------------------------------------------------------------------------
        # Thermal model: constant 25 °C ambient, battery registered as thermal node
        # ---------------------------------------------------------------------------
        thermal = AmbientThermalModel(T_ambient=25.0, components=[battery])

        # ---------------------------------------------------------------------------
        # Simulation loop
        # ---------------------------------------------------------------------------
        keys = ["soc", "v", "i", "T", "loss", "heat", "soh_Q", "soh_R", "power"]
        log = {k: np.empty(self.n_timesteps) for k in keys}

        for i, p in enumerate(power_profile):
            battery.step(float(p), self.dt)
            thermal.step(self.dt)  # update battery temperature after each step
            for k in keys:
                log[k][i] = getattr(battery.state, k)

        index = pd.date_range("2026-01-01", periods=self.n_timesteps, freq=f"{int(self.dt)}s")
        df = pd.DataFrame(log, index=index)

        print("\nFirst rows:")
        print(df.head().to_string())
        # print(
        #     f"\nFinal SOH_Q : {df['soh_Q'].iloc[-1]:.4f}  ({(1 - df['soh_Q'].iloc[-1])
        # * 100:.2f} % capacity fade)"
        # )
        print(f"Final SOH_R : {df['soh_R'].iloc[-1]:.4f}")
        #############

        # Populate all OpenMDAO outputs defined in this class and its parent classes,
        # pulling the time-series results from the simses battery run (``df_bat``).

        soc_ts = df["soc"].to_numpy()
        # Convert battery power (W) into the desired commodity rate units.
        # Sign convention: positive = discharge (out of storage), negative = charge.
        power_ts = om_units.convert_units(df["power"].to_numpy(), "W", self.commodity_rate_units)

        # --- BatteryPerformanceModel outputs ---
        outputs[f"{self.commodity}_auxiliary_demand"] = np.zeros(self.n_timesteps)

        # --- StoragePerformanceBase outputs ---
        outputs["storage_duration"] = (
            storage_capacity / discharge_rate if discharge_rate > 0 else 0.0
        )
        outputs["SOC"] = soc_ts * 100.0  # fraction -> percent
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
            outputs["capacity_factor"] = outputs[f"total_{self.commodity}_produced"] / (
                discharge_rate * self.n_timesteps * self.dt_amount
            )
            total_commodity_discharged = (
                outputs[f"storage_{self.commodity}_discharge"].sum() * self.dt_amount
            )
            outputs["standard_capacity_factor"] = total_commodity_discharged / (
                discharge_rate * self.n_timesteps * self.dt_amount
            )
