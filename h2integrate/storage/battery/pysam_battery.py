import numpy as np
import PySAM.BatteryTools as BatteryTools
import PySAM.BatteryStateful as BatteryStateful
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, range_val
from h2integrate.storage.storage_baseclass import (
    StoragePerformanceBase,
    StoragePerformanceBaseConfig,
)


@define(kw_only=True)
class PySAMBatteryPerformanceModelConfig(StoragePerformanceBaseConfig):
    """Configuration class for battery performance models.

    This class defines configuration parameters for simulating battery
    performance in PySAM system models. It includes
    specifications such as capacity, chemistry, state-of-charge limits,
    and reference module characteristics.

    Attributes:
        max_capacity (float): Maximum battery energy capacity in kilowatt-hours (kWh).
            Must be greater than zero.
        max_charge_rate (float): Rated power capacity of the battery in kilowatts (kW).
            Must be greater than zero.
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
        chemistry (str):
            Battery chemistry option. "LDES" has not been brought over from HOPP yet.
            Supported values include:

            - PySAM: ``"LFPGraphite"``, ``"LMOLTO"``, ``"LeadAcid"``, ``"NMCGraphite"``

        min_soc_fraction (float): Minimum allowable state of charge as a fraction (0 to 1).
        max_soc_fraction (float): Maximum allowable state of charge as a fraction (0 to 1).
        init_soc_fraction (float): Initial state of charge as a fraction (0 to 1).
        control_variable (str): Control mode for the PySAM battery, either ``"input_power"``
            or ``"input_current"``.
        ref_module_capacity (int | float, optional): Reference module capacity in kWh.
            Defaults to 400.
        ref_module_surface_area (int | float, optional): Reference module surface area in m².
            Defaults to 30.
        Cp (int | float, optional): Battery specific heat capacity [J/kg*K].
            Defaults to 900.
        battery_h (int | float, optional): Heat transfer between battery and
            environment [W/m2*K]. Defaults to 20.
        resistance (int | float, optional): Battery internal resistance [Ohm].
            Defaults to 0.001.
    """

    max_capacity: float = field(validator=gt_zero)
    max_charge_rate: float = field(validator=gt_zero)

    chemistry: str = field(
        validator=contains(["LFPGraphite", "LMOLTO", "LeadAcid", "NMCGraphite"]),
    )

    init_soc_fraction: float = field(validator=range_val(0, 1))
    control_variable: str = field(
        default="input_power", validator=contains(["input_power", "input_current"])
    )
    ref_module_capacity: int | float = field(default=400)
    ref_module_surface_area: int | float = field(default=30)
    Cp: int | float = field(default=900)
    battery_h: int | float = field(default=20)
    resistance: int | float = field(default=0.001)


class PySAMBatteryPerformanceModel(StoragePerformanceBase):
    """OpenMDAO component wrapping the PySAM Battery Performance model.

    This class integrates the NLR PySAM ``BatteryStateful`` model into
    an OpenMDAO component. It provides inputs and outputs for battery
    capacity, charge/discharge power, state of charge, and unmet or unused
    demand.

    The PySAM battery simulation does not always respect max and min charge
    bounds set by the user. It may exceed the bounds by up to 5% SOC.

    Attributes:
        system_model (``BatteryStateful``): Instance of the PySAM BatteryStateful model, initialized
            with the selected chemistry and configuration parameters.


    Methods:
        compute(inputs, outputs, discrete_inputs, discrete_outputs):
            Runs the PySAM BatteryStateful model for a simulation timestep,
            updating outputs such as SOC, charge/discharge limits, unmet
            demand, and unused commodities.
        _set_control_mode(control_mode=1.0, input_power=0.0, input_current=0.0,
            control_variable="input_power"):
            Sets the battery control mode (power or current).
    """

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        """Set up the PySAM Battery Performance model in OpenMDAO.

        Initializes the configuration, defines inputs/outputs for OpenMDAO,
        and creates a `BatteryStateful` instance with the selected chemistry.
        If dispatch connections are specified, it also sets up a discrete
        input for Pyomo solver integration.
        """
        self.config = PySAMBatteryPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        # Initialize the PySAM BatteryStateful model with defaults
        self.system_model = BatteryStateful.default(self.config.chemistry)

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """Run the PySAM Battery model for one simulation step.

        Configures the battery stateful model parameters (SOC limits, timestep,
        thermal properties, etc.), executes the simulation, and stores the
        results in OpenMDAO outputs.
        """

        # Size the battery based on inputs -> method brought from HOPP
        module_specs = {
            "capacity": self.config.ref_module_capacity,
            "surface_area": self.config.ref_module_surface_area,
        }

        BatteryTools.battery_model_sizing(
            self.system_model,
            inputs["max_charge_rate"][0],
            inputs["storage_capacity"][0],
            self.system_model.ParamsPack.nominal_voltage,
            module_specs=module_specs,
        )
        self.system_model.ParamsPack.h = self.config.battery_h
        self.system_model.ParamsPack.Cp = self.config.Cp
        self.system_model.ParamsCell.resistance = self.config.resistance
        self.system_model.ParamsCell.C_rate = (
            inputs["max_charge_rate"][0] / inputs["storage_capacity"][0]
        )

        # Minimum set of parameters to set to get statefulBattery to work
        self._set_control_mode()

        self.system_model.value("input_current", 0.0)
        self.system_model.value("dt_hr", self.dt_hr)
        self.system_model.value("minimum_SOC", self.config.min_soc_fraction * 100)
        self.system_model.value("maximum_SOC", self.config.max_soc_fraction * 100)
        self.system_model.value("initial_SOC", self.config.init_soc_fraction * 100)

        # Setup PySAM battery model using PySAM method
        self.system_model.setup()

        # Run PySAM battery model 1 timestep to initialize values
        self.system_model.value("dt_hr", self.dt_hr)
        self.system_model.value("input_power", 0.0)
        self.system_model.execute(0)

        outputs = self.run_storage(
            inputs["max_charge_rate"][0],
            inputs["max_charge_rate"][0],
            inputs["storage_capacity"][0],
            inputs,
            outputs,
            discrete_inputs,
        )

    def simulate(
        self,
        storage_dispatch_commands: list,
        charge_rate: float,
        discharge_rate: float,
        storage_capacity: float,
        sim_start_index: int = 0,
    ):
        """Run the PySAM BatteryStateful model over a control window.

        Applies a sequence of dispatch commands (positive = discharge, negative = charge)
        one timestep at a time. Each command is clipped to allowable instantaneous
        charge or discharge limits derived from:

            1. Rated power (``config.max_charge_rate``)
            2. PySAM internal estimates (``P_chargeable`` and ``P_dischargeable``)
            3. Remaining energy headroom vs. SOC bounds

        The simulate method is much of what would normally be in the ``compute()`` method
        of a component, but is separated into its own function here to allow the ``dispatch()``
        method to manage calls to the performance model.

        Args:
            storage_dispatch_commands : Sequence[float]
                Commanded power per timestep (kW). Negative = charge, positive = discharge.
                Length should be = ``config.n_control_window``.
            control_variable : str
                PySAM control input to set each step ("input_power" or "input_current").
            sim_start_index : int, optional
                Starting index for writing into persistent output arrays (default 0).

        Returns:
            tuple[np.ndarray, np.ndarray]: Battery power (kW) and SOC (%) per timestep.

        Notes:
            - SOC bounds may still be exceeded slightly due to PySAM internal dynamics.
        """

        # Loop through the provided input power/current (decided by control_variable)
        self.system_model.value("dt_hr", self.dt_hr)

        # initialize outputs
        n = len(storage_dispatch_commands)
        storage_power_out_timesteps = np.zeros(n)
        soc_timesteps = np.zeros(n)

        # get constant battery parameters needed during all time steps
        soc_max = self.system_model.value("maximum_SOC") / 100.0
        soc_min = self.system_model.value("minimum_SOC") / 100.0

        commands = np.asarray(storage_dispatch_commands, dtype=float)

        for t, cmd in enumerate(commands):
            # get storage SOC at time t as a fraction
            soc = self.system_model.value("SOC") / 100.0

            if cmd < 0.0:
                # --- Charging ---
                # headroom: how much more commodity the storage can accept,
                # expressed as a rate (commodity_rate_units).
                headroom = (soc_max - soc) * storage_capacity / self.dt_hr

                # Calculate the max charge according to the charge rate and the simulation
                max_charge_input = min([charge_rate, -self.system_model.value("P_chargeable")])

                # Clip to the most restrictive limit,
                # max(0, ...) guards against negative headroom when SOC
                # slightly exceeds soc_max.
                actual_charge = max(0.0, min(headroom, max_charge_input, -cmd))

                # Update the charge command for the PySAM batttery
                cmd = -actual_charge

            else:
                # --- Discharging ---
                # headroom: how much commodity can still be drawn before
                # hitting the minimum SOC, expressed as a rate.
                headroom = (soc - soc_min) * storage_capacity / self.dt_hr

                # Calculate the max discharge according to the discharge rate and the simulation
                max_discharge_input = min(
                    [discharge_rate, self.system_model.value("P_dischargeable")]
                )

                # Clip and apply discharge efficiency.
                actual_discharge = max(0.0, min(headroom, max_discharge_input, cmd))

                # Update the discharge command for the PySAM batttery
                cmd = actual_discharge

            # Set the input variable to the desired value
            self.system_model.value(self.config.control_variable, cmd)

            # Simulate the PySAM BatteryStateful model
            self.system_model.execute(0)

            # Save outputs at time t based on the simulation
            storage_power_out_timesteps[t] = self.system_model.value("P")
            soc_timesteps[t] = self.system_model.value("SOC")

        return storage_power_out_timesteps, soc_timesteps

    def _set_control_mode(
        self,
        control_mode: float = 1.0,
        input_power: float = 0.0,
        input_current: float = 0.0,
        control_variable: str = "input_power",
    ):
        """Set the control mode for the PySAM BatteryStateful model.

        Configures whether the battery operates in power-control or
        current-control mode and initializes input values.

        Args:
            control_mode (float, optional):
                Mode flag: ``1.0`` for power control, ``0.0`` for current control.
                Defaults to 1.0.
            input_power (float, optional):
                Initial power input (kW). Defaults to 0.0.
            input_current (float, optional):
                Initial current input (A). Defaults to 0.0.
            control_variable (str, optional):
                Control variable name, either ``"input_power"`` or ``"input_current"``.
                Defaults to "input_power".
        """
        if isinstance(self.system_model, BatteryStateful.BatteryStateful):
            # Power control = 1.0, current control = 0.0
            self.system_model.value("control_mode", control_mode)
            # Need initial values
            self.system_model.value("input_power", input_power)
            self.system_model.value("input_current", input_current)
            # Either `input_power` or `input_current`; need to adjust `control_mode` above
            self.control_variable = control_variable
