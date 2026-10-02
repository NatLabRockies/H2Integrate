import math

import numpy as np
import pandas as pd


"""
Integration notes:

- added container model (should not need ambient
- added hvac model
- see init update
- may need time series, but may not
- prefer running at one minute
- may need to upsample data before running and then down sample
    since simses does not work with hourly
- expecting hourly input, but giving minute output
- _DEG_Scale changed as well: would like a better way to define,
    but current values should be reasonable across a range of
        operating conditions
- replace power profile with charge/discharge command
    (- discharge, + charge)
- may need to allow simses to run at alternate
    timestep internally - model-specific dt
- key update
    - hvac model
    - battery thermal model
        - do not change container properties
        - connect lat long to SolarConfig
        - azimuth - not sure what it is doing exactly , maybe whether
            container is level? Xi to check
        - initial temp and set point can be set or not and left alone
        - should not change T batt safe range
        - max power kw is for HVAC and is user defined value, but suggest not changing much
        - cop snominal values hould probably not change
        - container.add_component(battery) connects the battery and container models
        - note additional loging params

"""

"""
# NOTE: ``simses.battery`` must be imported before ``simses.degradation`` to avoid a
# circular import within simses (>=2.1.1): importing ``simses.degradation`` first leaves
# ``simses.degradation.calendar`` partially initialized when ``simses.battery.cell`` pulls
# in ``simses.degradation.degradation``. Importing the battery package first fully loads
# both sub-packages in a safe order. (Plain ``import`` sorts above ``from`` imports.)
import simses.battery  # noqa: F401  (import-order side effect; see note above)
"""

from attrs import field, define, validators
from openmdao.utils import units as om_units


# isort: off
from simses.battery.state import BatteryState
from simses.battery.battery import Battery
from simses.degradation import DegradationModel
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
# isort: on

from simses.thermal import SolarConfig, solar_heat_load

from h2integrate.core.utilities import merge_shared_inputs, build_time_series_from_plant_config
from h2integrate.storage.storage_baseclass import (
    StoragePerformanceBase,
    StoragePerformanceBaseConfig,
)
from h2integrate.storage.battery.battery_with_degredation.container import (
    ContainerLayer,
    VariableCopHvac,
    ThermostatStrategy,
    ContainerProperties,
    ContainerThermalModel,
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

    max_capacity: float = field(validator=validators.gt(0))
    max_charge_rate: float = field(validator=validators.gt(0))

    init_soc_fraction: float = field(validator=(validators.ge(0), validators.le(1)))

    commodity_amount_units: str = field(default=None)
    max_discharge_rate: float | None = field(default=None)
    charge_equals_discharge: bool = field(default=True)

    charge_efficiency: float | None = field(
        default=None,
        validator=validators.optional((validators.ge(0), validators.le(1))),
    )
    discharge_efficiency: float | None = field(
        default=None,
        validator=validators.optional((validators.ge(0), validators.le(1))),
    )
    round_trip_efficiency: float | None = field(
        default=None,
        validator=validators.optional((validators.ge(0), validators.le(1))),
    )

    deg_scale: float = field(default=0.115, validator=(validators.ge(0), validators.le(1)))
    eol_soh_capacity: float = field(default=0.8, validator=(validators.ge(0), validators.le(1)))
    # TODO convert from power and energy ratings (see math in chat)
    series_count: int = field(default=336, converter=int, validator=validators.gt(0))
    parallel_count: int = field(default=16, converter=int, validator=validators.gt(0))
    battery_temperature_c: float = field(default=25.0)
    converter_efficiency: float = field(
        default=0.96, validator=(validators.ge(0), validators.le(1))
    )
    converter_max_power: float = field(default=2400.0, validator=validators.gt(0))

    # Container HVAC / thermostat parameters (container geometry itself is fixed; see
    # self.container_properties).
    hvac_cop_cooling_nominal: float = field(default=3.2, validator=validators.gt(0))
    hvac_cop_heating_nominal: float = field(default=3.8, validator=validators.gt(0))
    hvac_max_power: float = field(default=12.0, validator=validators.gt(0))
    thermostat_setpoint: float = field(default=25.0)
    thermostat_deadband: float = field(default=5.0, validator=validators.gt(0))
    # The container's thin wall layers make its forward-Euler thermal integration
    # unstable at large dt; it is sub-stepped internally at up to this duration.
    thermal_substep_max: float = field(default=60.0, validator=validators.gt(0))

    # Container orientation for solar heat-gain pre-computation (container geometry itself
    # remains fixed; see self.container_properties). Site latitude/longitude are not
    # tech_config parameters; they must be connected from the plant's site info (see
    # the `latitude`/`longitude` inputs in setup()).
    azimuth: float = field(default=0.0)

    # Battery cell temperature range for safe operation; commanded power is forced to
    # zero for any timestep where the battery temperature falls outside this range.
    battery_temp_safe_lower: float = field(default=15.0)
    battery_temp_safe_upper: float = field(default=45.0)

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

        # Tesla Megapack 2XL enclosure geometry/wall layers (fixed; tied to the 336s x 16p pack
        # topology below, so not exposed as tech_config parameters).
        # ---------------------------------------------------------------------------
        # Tesla Megapack 2 XL battery pack
        #
        # Physical layout  : 24 modules max; each module = 3 trays (112 cells) = 336 series cells
        # Configuration    : (336s)(16p)  (16 modules in parallel)
        # DC bus voltage   : (336)(3.2 V) = 1075.2 V
        # Nominal energy   : (336)(3.2)(280)(16) = 4817 kWh  (0-100 % SOC)
        # Usable (10-90 %) : (0.8)(4817) = 3854 kWh  (matches 2-hr AC discharge spec)
        # Inverter         : FixedEfficiency(0.96), max 2400 kW  → converter RTE 92.2 %
        # ---------------------------------------------------------------------------
        self.container_properties = ContainerProperties(
            length=9.118,
            width=1.659,
            height=2.800,
            # Inner and outer surface convection coefficient in W/m²K.
            h_inner=5.0,
            h_outer=15.0,
            # thickness, conductivity, density, and specific heat by layer
            inner=ContainerLayer(0.001, 200, 2700, 900),
            mid=ContainerLayer(0.06, 0.04, 30, 1000),
            outer=ContainerLayer(0.002, 50, 7800, 500),
        )

        super().setup()

        self.add_discrete_input(
            "solar_resource_data",
            val={},
            desc="Solar resource data dictionary",
        )

        # Container HVAC / thermostat inputs (geometry is fixed; see self.container_properties).
        self.add_input(
            "hvac_cop_cooling_nominal",
            val=self.config.hvac_cop_cooling_nominal,
            units="unitless",
            desc="HVAC cooling coefficient of performance at nominal conditions",
        )
        self.add_input(
            "hvac_cop_heating_nominal",
            val=self.config.hvac_cop_heating_nominal,
            units="unitless",
            desc="HVAC heating coefficient of performance at nominal conditions",
        )
        self.add_input(
            "hvac_max_power",
            val=self.config.hvac_max_power,
            units=self.commodity_rate_units,
            desc="Maximum HVAC thermal power (heating and cooling)",
        )
        self.add_input(
            "thermostat_setpoint",
            val=self.config.thermostat_setpoint,
            units="degC",
            desc="Target container internal air temperature",
        )
        self.add_input(
            "thermostat_deadband",
            val=self.config.thermostat_deadband,
            units="degC",
            desc="Thermostat dead-band half-width",
        )
        self.add_input(
            "thermal_substep_max",
            val=self.config.thermal_substep_max,
            units="s",
            desc="Maximum internal substep duration for the container thermal simulation",
        )
        self.add_input(
            "latitude",
            val=0.0,
            shape=1,
            require_connection=True,
            units="deg",
            desc="Site latitude for solar heat-gain pre-computation (from plant site info)",
        )
        self.add_input(
            "longitude",
            val=0.0,
            shape=1,
            require_connection=True,
            units="deg",
            desc="Site longitude for solar heat-gain pre-computation (from plant site info)",
        )
        self.add_input(
            "azimuth",
            val=self.config.azimuth,
            units="deg",
            desc="Container orientation (compass bearing of the north face)",
        )
        self.add_input(
            "battery_temp_safe_lower",
            val=self.config.battery_temp_safe_lower,
            units="degC",
            desc="Battery output is forced to zero below this cell temperature",
        )
        self.add_input(
            "battery_temp_safe_upper",
            val=self.config.battery_temp_safe_upper,
            units="degC",
            desc="Battery output is forced to zero above this cell temperature",
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
            "power_ac", shape=self.n_timesteps, units="W", desc="AC-side power (positive = charge)"
        )
        self.add_output(
            "power_dc", shape=self.n_timesteps, units="W", desc="DC-side power (positive = charge)"
        )
        self.add_output("converter_loss", shape=self.n_timesteps, units="W", desc="Converter loss")
        self.add_output(
            "container_air_temperature",
            shape=self.n_timesteps,
            units="degC",
            desc="Container internal air temperature",
        )
        self.add_output(
            "container_wall_temperature_inner",
            shape=self.n_timesteps,
            units="degC",
            desc="Container inner wall layer temperature",
        )
        self.add_output(
            "container_wall_temperature_mid",
            shape=self.n_timesteps,
            units="degC",
            desc="Container middle wall layer temperature",
        )
        self.add_output(
            "container_wall_temperature_outer",
            shape=self.n_timesteps,
            units="degC",
            desc="Container outer wall layer temperature",
        )
        self.add_output(
            "solar_heat_gain",
            shape=self.n_timesteps,
            units="W",
            desc="Solar irradiance heat load absorbed by the container",
        )
        self.add_output(
            "hvac_thermal_power",
            shape=self.n_timesteps,
            units="W",
            desc="HVAC thermal power delivered to container air (+heating/-cooling)",
        )
        self.add_output(
            "hvac_electrical_power",
            shape=self.n_timesteps,
            units="W",
            desc="HVAC electrical power consumption",
        )
        self.add_output(
            "system_derated",
            shape=self.n_timesteps,
            units="unitless",
            desc="1 where battery output was forced to zero by the safe temperature interlock",
        )

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

        ### from Ankit

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
        # Thermal model: container enclosure (fixed Megapack 2XL geometry) with a
        # thermostatically-controlled HVAC unit; battery registered as a thermal node.
        # Ambient temperature and solar GHI are taken from the resource weather data.
        # ---------------------------------------------------------------------------
        resource_data = discrete_inputs["solar_resource_data"]
        missing_keys = [k for k in ("temperature", "ghi") if resource_data.get(k) is None]
        if missing_keys:
            raise ValueError(
                f"{self.msginfo}: the container thermal model requires ambient temperature and "
                f"GHI data, but 'solar_resource_data' is missing: {missing_keys}. Connect a "
                "resource providing this data (e.g. via site_to_tech_connections) to this "
                "technology."
            )
        ambient_temperature = np.asarray(resource_data["temperature"], dtype=float)

        time_index = pd.DatetimeIndex(
            build_time_series_from_plant_config(self.options["plant_config"])
        )
        ghi_series = pd.Series(np.asarray(resource_data["ghi"], dtype=float), index=time_index)
        solar_config = SolarConfig(
            latitude=float(inputs["latitude"][0]),
            longitude=float(inputs["longitude"][0]),
            azimuth=float(inputs["azimuth"][0]),
        )
        q_solar = solar_heat_load(ghi_series, self.container_properties, solar_config).to_numpy()

        battery_temp_safe_lower = float(inputs["battery_temp_safe_lower"][0])
        battery_temp_safe_upper = float(inputs["battery_temp_safe_upper"][0])

        hvac_max_power_w = om_units.convert_units(
            float(inputs["hvac_max_power"][0]), self.commodity_rate_units, "W"
        )
        tms = ThermostatStrategy(
            T_setpoint=float(inputs["thermostat_setpoint"][0]),
            max_power=hvac_max_power_w,
            threshold=float(inputs["thermostat_deadband"][0]),
        )
        hvac = VariableCopHvac(
            cop_cooling_nominal=float(inputs["hvac_cop_cooling_nominal"][0]),
            cop_heating_nominal=float(inputs["hvac_cop_heating_nominal"][0]),
            max_heating_capacity=hvac_max_power_w,
            max_cooling_capacity=hvac_max_power_w,
        )
        thermal = ContainerThermalModel(
            self.container_properties,
            T_ambient=float(ambient_temperature[0]),
            T_initial=float(inputs["thermostat_setpoint"][0]),
            hvac=hvac,
            tms=tms,
        )
        thermal.add_component(battery)

        # The container thermal network is stiff (thin wall layers); sub-step it so the
        # forward-Euler integration stays stable regardless of the outer simulation dt.
        n_thermal_substeps = max(1, math.ceil(self.dt / float(inputs["thermal_substep_max"][0])))
        thermal_sub_dt = self.dt / n_thermal_substeps

        # ---------------------------------------------------------------------------
        # Simulation loop
        # ---------------------------------------------------------------------------
        keys = ["soc", "v", "i", "T", "loss", "heat", "soh_Q", "soh_R"]
        log = {k: np.empty(self.n_timesteps) for k in keys}
        power_ac = np.empty(self.n_timesteps)
        power_dc = np.empty(self.n_timesteps)
        conv_loss = np.empty(self.n_timesteps)
        container_T_air = np.empty(self.n_timesteps)
        container_T_in = np.empty(self.n_timesteps)
        container_T_mid = np.empty(self.n_timesteps)
        container_T_out = np.empty(self.n_timesteps)
        hvac_power_th = np.empty(self.n_timesteps)
        hvac_power_el = np.empty(self.n_timesteps)
        system_derated = np.zeros(self.n_timesteps)

        for i, p in enumerate(power_profile):
            # Safety interlock: force commanded power to zero if the battery cell
            # temperature (from the prior step) is outside the safe operating range.
            current_batt_temp = battery.state.T
            if (
                current_batt_temp > battery_temp_safe_upper
                or current_batt_temp < battery_temp_safe_lower
            ):
                p_executed = 0.0
                system_derated[i] = 1.0
            else:
                p_executed = float(p)

            # H2I sign (+discharge) -> SimSES AC sign (+charge)
            converter.step(
                -om_units.convert_units(p_executed, self.commodity_rate_units, "W"), self.dt
            )
            thermal.T_ambient = float(ambient_temperature[i])
            thermal.Q_solar = float(q_solar[i])
            for _ in range(n_thermal_substeps):
                thermal.step(thermal_sub_dt)  # update battery temperature after each substep
            for k in keys:
                log[k][i] = getattr(battery.state, k)
            power_ac[i] = converter.state.power  # AC power (W), positive = charge
            power_dc[i] = battery.state.power  # AC power (W), positive = charge
            conv_loss[i] = converter.state.loss
            container_T_air[i] = thermal.state.T_air
            container_T_in[i] = thermal.state.T_in
            container_T_mid[i] = thermal.state.T_mid
            container_T_out[i] = thermal.state.T_out
            hvac_power_th[i] = thermal.state.power_th
            hvac_power_el[i] = thermal.state.power_el

        #############

        # Expose the full SimSES timeseries as OpenMDAO outputs for downstream
        # diagnostics/plotting
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
        outputs["container_air_temperature"] = container_T_air
        outputs["container_wall_temperature_inner"] = container_T_in
        outputs["container_wall_temperature_mid"] = container_T_mid
        outputs["container_wall_temperature_outer"] = container_T_out
        outputs["solar_heat_gain"] = q_solar
        outputs["hvac_thermal_power"] = hvac_power_th
        outputs["hvac_electrical_power"] = hvac_power_el
        outputs["system_derated"] = system_derated

        # Populate all OpenMDAO outputs defined in this class and its parent classes.
        # Convert SimSES AC power (W, +charge) back to H2I convention
        # (commodity_rate_units, +discharge).
        soc_ts = log["soc"]
        power_ts = -om_units.convert_units(power_ac, "W", self.commodity_rate_units)

        # --- BatteryPerformanceModel outputs ---
        outputs[f"{self.commodity}_auxiliary_demand"] = om_units.convert_units(
            hvac_power_el, "W", self.commodity_rate_units
        )

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
        outputs["operational_life"] = self.plant_life

        if discharge_rate <= 0:
            outputs["capacity_factor"] = 0.0
            outputs["standard_capacity_factor"] = 0.0
            outputs["replacement_schedule"] = np.zeros(self.plant_life)
        else:
            # Gross discharge timeseries (commodity_rate_units, discharge only).
            discharge_ts = outputs[f"storage_{self.commodity}_discharge"]
            total_commodity_discharged = discharge_ts.sum() * self.dt_amount

            # Scalar average discharge capacity factor over the whole simulation.
            outputs["standard_capacity_factor"] = total_commodity_discharged / (
                discharge_rate * self.n_timesteps * self.dt_amount
            )

            # Per-year capacity factor and replacement schedule projected across the plant
            # life from the simulated discharge and capacity-SOH timeseries. Uses the shared
            # base-class method: when the SOH reaches end of life (eol_soh_capacity) the
            # battery is replaced and the degradation/capacity-factor cycle repeats.
            annual_cf, replacement_schedule = self.calculate_annual_cf_and_replacement_schedule(
                performance_timeseries=discharge_ts,
                rated_performance=discharge_rate,
                state_of_health_timeseries=log["soh_Q"],
                eol_soh=self.config.eol_soh_capacity,
            )
            outputs["capacity_factor"] = annual_cf
            outputs["replacement_schedule"] = replacement_schedule
