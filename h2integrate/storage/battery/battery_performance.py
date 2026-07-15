import numpy as np
import pandas as pd
from attrs import field, define
from openmdao.utils import units as om_units
from simses.battery.battery import Battery
from simses.degradation.state import DegradationState
from simses.model.cell.sony_lfp import SonyLFP

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

    def internal_resistance(self, state):
        return super().internal_resistance(state) * self._SCALE


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

        ### from Ankit
        cell = LFP280Ah()

        battery = Battery(
            cell=cell,
            circuit=(239, 18),
            initial_states={"start_soc": 0.5, "start_T": 25.0},
            degradation=LFP280Ah.default_degradation_model(
                initial_soc=0.5,
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

        dt = self.dt_hr * 60.0

        # power_profile = inputs[f"{self.commodity}_in"]
        power_profile = inputs[f"{self.commodity}_set_point"]

        log = {
            k: np.empty(self.n_timesteps)
            for k in ["soc", "v", "i", "T", "loss", "heat", "soh_Q", "soh_R", "power"]
        }
        for i, p in enumerate(power_profile):
            battery.step(float(p), dt)
            for k in log:
                log[k][i] = getattr(battery.state, k)

        index = pd.date_range("2025-01-01", periods=self.n_timesteps, freq=f"{int(dt)}s")
        df_bat = pd.DataFrame(log, index=index)
        print("\nFirst rows:")
        print(df_bat.head().to_string())

        #############

        # Populate all OpenMDAO outputs defined in this class and its parent classes,
        # pulling the time-series results from the simses battery run (``df_bat``).

        soc_ts = df_bat["soc"].to_numpy()
        # Convert battery power (W) into the desired commodity rate units.
        # Sign convention: positive = discharge (out of storage), negative = charge.
        power_ts = om_units.convert_units(
            df_bat["power"].to_numpy(), "W", self.commodity_rate_units
        )

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
