from dataclasses import asdict, dataclass
from collections.abc import Sequence

import numpy as np
import PySAM.BatteryTools as BatteryTools
import PySAM.BatteryStateful as BatteryStateful
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, range_val
from h2integrate.storage.battery.battery_baseclass import BatteryPerformanceBaseClass


@dataclass
class BatteryOutputs:
    I: Sequence  # noqa: E741
    P: Sequence
    Q: Sequence
    SOC: Sequence
    T_batt: Sequence
    gen: Sequence
    n_cycles: Sequence
    P_chargeable: Sequence
    P_dischargeable: Sequence
    unmet_demand: list[float]
    unused_commodity: list[float]

    """
    Container for simulated outputs from the `BatteryStateful` and H2I dispatch models.

    Attributes:
        I (Sequence): Battery current [A] per timestep.
        P (Sequence): Battery power [kW] per timestep.
        Q (Sequence): Battery capacity [Ah] per timestep.
        SOC (Sequence): State of charge [%] per timestep.
        T_batt (Sequence): Battery temperature [°C] per timestep.
        gen (Sequence): Generated power [kW] per timestep.
        n_cycles (Sequence): Cumulative rainflow cycles since start of simulation [1].
        P_chargeable (Sequence): Maximum estimated chargeable power [kW] per timestep.
        P_dischargeable (Sequence): Maximum estimated dischargeable power [kW] per timestep.

        unmet_demand (list[float]): Unmet demand [kW] per timestep.
        unused_commodity (list[float]): Unused available commodity [kW] per timestep.
    """

    def __init__(self, n_timesteps, n_control_window):
        """Class for storing stateful battery and dispatch outputs."""
        self.stateful_attributes = [
            "I",
            "P",
            "Q",
            "SOC",
            "T_batt",
            "n_cycles",
            "P_chargeable",
            "P_dischargeable",
        ]
        for attr in self.stateful_attributes:
            setattr(self, attr, [0.0] * n_timesteps)

        self.dispatch_lifecycles_per_control_window = [None] * int(n_timesteps / n_control_window)

        self.component_attributes = ["unmet_demand", "unused_commodity"]
        for attr in self.component_attributes:
            setattr(self, attr, [0.0] * n_timesteps)

    def export(self):
        return asdict(self)


@define(kw_only=True)
class PySAMBatteryPerformanceModelConfig(BaseConfig):
    """Configuration class for battery performance models.

    This class defines configuration parameters for simulating battery
    performance in PySAM system models. It includes
    specifications such as capacity, chemistry, state-of-charge limits,
    and reference module characteristics.

    Attributes:
        max_capacity (float):
            Maximum battery energy capacity in kilowatt-hours (kWh).
            Must be greater than zero.
        max_charge_rate (float):
            Rated power capacity of the battery in kilowatts (kW).
            Must be greater than zero.
        system_model_source (str):
            Source software for the system model. "hopp" source has not been brought
            over from HOPP yet. Options are:
                - "pysam"
        chemistry (str):
            Battery chemistry option. "LDES" has not been brought over from HOPP yet.
            Supported values include:
                - PySAM: "LFPGraphite", "LMOLTO", "LeadAcid", "NMCGraphite"
        min_charge_percent (float):
            Minimum allowable state of charge as a fraction (0 to 1).
        max_charge_percent (float):
            Maximum allowable state of charge as a fraction (0 to 1).
        init_charge_percent (float):
            Initial state of charge as a fraction (0 to 1).
        n_control_window (int, optional):
            Number of timesteps in the control window. Defaults to 24.
        n_horizon_window (int, optional):
            Number of timesteps in the horizon window. Defaults to 48.
        control_variable (str):
            Control mode for the PySAM battery, either ``"input_power"``
            or ``"input_current"``.
        ref_module_capacity (int | float, optional):
            Reference module capacity in kilowatt-hours (kWh).
            Defaults to 400.
        ref_module_surface_area (int | float, optional):
            Reference module surface area in square meters (m²).
            Defaults to 30.
    """

    max_capacity: float = field(validator=gt_zero)
    max_charge_rate: float = field(validator=gt_zero)

    system_model_source: str = field(validator=contains(["pysam"]))
    chemistry: str = field(
        validator=contains(["LFPGraphite", "LMOLTO", "LeadAcid", "NMCGraphite"]),
    )
    min_charge_percent: float = field(validator=range_val(0, 1))
    max_charge_percent: float = field(validator=range_val(0, 1))
    init_charge_percent: float = field(validator=range_val(0, 1))
    n_control_window: int = field(validator=gt_zero, default=24)
    n_horizon_window: int = field(validator=gt_zero, default=48)
    control_variable: str = field(
        default="input_power", validator=contains(["input_power", "input_current"])
    )
    ref_module_capacity: int | float = field(default=400)
    ref_module_surface_area: int | float = field(default=30)


class PySAMBatteryPerformanceModel(BatteryPerformanceBaseClass):
    """OpenMDAO component wrapping the PySAM Battery Performance model.

    This class integrates the NREL PySAM `BatteryStateful` model into
    an OpenMDAO component. It provides inputs and outputs for battery
    capacity, charge/discharge power, state of charge, and unmet or unused
    demand.

    The PySAM battery simulation does not always respect max and min charge
    bounds set by the user. It may exceed the bounds by up to 5% SOC.

    Attributes:
        config (PySAMBatteryPerformanceModelConfig):
            Configuration parameters for the battery performance model.
        system_model (BatteryStateful):
            Instance of the PySAM BatteryStateful model, initialized with
            the selected chemistry and configuration parameters.
        outputs (BatteryOutputs):
            Container for simulation outputs such as SOC, chargeable/dischargeable
            power, unmet demand, and unused commodities.
        unmet_demand (float):
            Tracks unmet demand during simulation (kW).
        unused_commodity (float):
            Tracks unused commodity during simulation (kW).

    Inputs:
        max_charge_rate (float):
            Battery charge rate in kilowatts per hour (kW).
        storage_capacity (float):
            Total energy storage capacity in kilowatt-hours (kWh).
        electricity_demand (ndarray):
            Power demand time series (kW).
        electricity_in (ndarray):
            Commanded input electricity (kW), typically from dispatch.

    Outputs:
        P_chargeable (ndarray):
            Maximum chargeable power (kW).
        P_dischargeable (ndarray):
            Maximum dischargeable power (kW).
        unmet_demand_out (ndarray):
            Remaining unmet demand after discharge (kW).
        unused_commodity_out (ndarray):
            Unused energy not absorbed by the battery (kW).
        electricity_out (ndarray):
            Dispatched electricity to meet demand (kW), including electricity from
            electricity_in that was never used to charge the battery and
            battery_electricity_discharge.
        SOC (ndarray):
            Battery state of charge (%).
        battery_electricity_discharge (ndarray):
            Electricity output from the battery model (kW).

    Methods:
        setup():
            Defines model inputs, outputs, configuration, and connections
            to plant-level dispatch (if applicable).
        compute(inputs, outputs, discrete_inputs, discrete_outputs):
            Runs the PySAM BatteryStateful model for a simulation timestep,
            updating outputs such as SOC, charge/discharge limits, unmet
            demand, and unused commodities.
        simulate(electricity_in, electricity_demand, time_step_duration, control_variable,
            sim_start_index=0):
            Simulates the battery behavior across timesteps using either
            input power or input current as control. This method is similar to what is
            provided in typical compute methods in H2Integrate for running models, but
            needs to be a separate method here to allow the dispatch function to call
            and manage the performance model.
        _set_control_mode(control_mode=1.0, input_power=0.0, input_current=0.0,
            control_variable="input_power"):
            Sets the battery control mode (power or current).

    Notes:
        - Default timestep is 1 hour (``dt=1.0``).
        - State of charge (SOC) bounds are set using the configuration's
          ``min_charge_percent`` and ``max_charge_percent``.
        - If a Pyomo dispatch solver is provided, the battery will simulate
          dispatch decisions using solver inputs.
    """

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
        )

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units="kW",
            desc="Battery charge rate",
        )

        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units="kW*h",
            desc="Battery storage capacity",
        )

        BatteryPerformanceBaseClass.setup(self)

        self.add_input(
            "electricity_demand",
            val=0.0,
            copy_shape="electricity_in",
            units="kW",
            desc="Power demand",
        )

        self.add_output(
            "P_chargeable",
            val=0.0,
            copy_shape="electricity_in",
            units="kW",
            desc="Estimated max chargeable power",
        )

        self.add_output(
            "P_dischargeable",
            val=0.0,
            copy_shape="electricity_in",
            units="kW",
            desc="Estimated max dischargeable power",
        )

        self.add_output(
            "unmet_electricity_demand_out",
            val=0.0,
            copy_shape="electricity_in",
            units="kW",
            desc="Unmet power demand",
        )

        self.add_output(
            "unused_electricity_out",
            val=0.0,
            copy_shape="electricity_in",
            units="kW",
            desc="Unused generated commodity",
        )

        # Initialize the PySAM BatteryStateful model with defaults
        self.system_model = BatteryStateful.default(self.config.chemistry)

        n_timesteps = int(
            self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        )  # self.config.n_timesteps
        self.dt_hr = int(self.options["plant_config"]["plant"]["simulation"]["dt"]) / (
            60**2
        )  # convert from seconds to hours
        n_control_window = self.config.n_control_window

        # Setup outputs for the battery model to be stored during the compute method
        self.outputs = BatteryOutputs(n_timesteps=n_timesteps, n_control_window=n_control_window)

        # create inputs for pyomo control model
        if "tech_to_dispatch_connections" in self.options["plant_config"]:
            # get technology group name
            # TODO: The split below seems brittle
            self.tech_group_name = self.pathname.split(".")
            for _source_tech, intended_dispatch_tech in self.options["plant_config"][
                "tech_to_dispatch_connections"
            ]:
                if any(intended_dispatch_tech in name for name in self.tech_group_name):
                    self.add_discrete_input("pyomo_dispatch_solver", val=dummy_function)
                    break

        self.unmet_demand = 0.0
        self.unused_commodity = 0.0

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """Run the PySAM Battery model for one simulation step.

        Configures the battery stateful model parameters (SOC limits, timestep,
        thermal properties, etc.), executes the simulation, and stores the
        results in OpenMDAO outputs.

        Args:
            inputs (dict):
                Continuous input values (e.g., electricity_in, electricity_demand).
            outputs (dict):
                Dictionary where model outputs (SOC, P_chargeable, unmet demand, etc.)
                are written.
            discrete_inputs (dict):
                Discrete inputs such as control mode or Pyomo solver.
            discrete_outputs (dict):
                Discrete outputs (unused in this component).
        """
        # Size the battery based on inputs -> method brought from HOPP
        module_specs = {
            "capacity": self.config.ref_module_capacity,
            "surface_area": self.config.ref_module_surface_area,
        }

        BatteryTools.battery_model_sizing(
            self.system_model,
            self.config.max_charge_rate,
            self.config.max_capacity,
            self.system_model.ParamsPack.nominal_voltage,
            module_specs=module_specs,
        )
        self.system_model.ParamsPack.h = 20
        self.system_model.ParamsPack.Cp = 900
        self.system_model.ParamsCell.resistance = 0.001
        self.system_model.ParamsCell.C_rate = (
            inputs["max_charge_rate"][0] / inputs["storage_capacity"][0]
        )

        # Minimum set of parameters to set to get statefulBattery to work
        self._set_control_mode()

        self.system_model.value("input_current", 0.0)
        self.system_model.value("dt_hr", self.dt_hr)
        self.system_model.value("minimum_SOC", self.config.min_charge_percent * 100)
        self.system_model.value("maximum_SOC", self.config.max_charge_percent * 100)
        self.system_model.value("initial_SOC", self.config.init_charge_percent * 100)

        # Setup PySAM battery model using PySAM method
        self.system_model.setup()

        # Run PySAM battery model 1 timestep to initialize values
        self.system_model.value("dt_hr", self.dt_hr)
        self.system_model.value("input_power", 0.0)
        self.system_model.execute(0)

        if "pyomo_dispatch_solver" in discrete_inputs:
            # Simulate the battery with provided dispatch inputs
            dispatch = discrete_inputs["pyomo_dispatch_solver"]
            kwargs = {
                "time_step_duration": self.dt_hr,
                "control_variable": self.config.control_variable,
            }
            (
                total_power_out,
                battery_power_out,
                unmet_demand,
                unused_commodity,
                soc,
            ) = dispatch(self.simulate, kwargs, inputs)

        else:
            # Simulate the battery with provided inputs and no controller.
            # This essentially asks for discharge when demand exceeds input
            # and requests charge when input exceeds demand

            # estimate required dispatch commands
            pseudo_commands = inputs["electricity_demand"] - inputs["electricity_in"]

            battery_power, soc = self.simulate(
                storage_dispatch_commands=pseudo_commands,
                time_step_duration=self.dt_hr,
                control_variable=self.config.control_variable,
            )
            n_time_steps = len(inputs["electricity_demand"])

            # determine battery discharge
            self.outputs.P = battery_power
            battery_power_out = [np.max([0, battery_power[i]]) for i in range(n_time_steps)]

            # calculate combined power out from inflow source and battery (note: battery_power is
            # negative when charging)
            combined_power_out = inputs["electricity_in"] + battery_power

            # find the total power out to meet demand
            total_power_out = np.minimum(inputs["electricity_demand"], combined_power_out)

            # determine how much of the inflow electricity was unused
            self.outputs.unused_commodity = [
                np.max([0, combined_power_out[i] - inputs["electricity_demand"][i]])
                for i in range(n_time_steps)
            ]
            unused_commodity = self.outputs.unused_commodity

            # determine how much demand was not met
            self.outputs.unmet_demand = [
                np.max([0, inputs["electricity_demand"][i] - combined_power_out[i]])
                for i in range(n_time_steps)
            ]
            unmet_demand = self.outputs.unmet_demand

        outputs["unmet_electricity_demand_out"] = unmet_demand
        outputs["unused_electricity_out"] = unused_commodity
        outputs["battery_electricity_discharge"] = battery_power_out
        outputs["electricity_out"] = total_power_out
        outputs["SOC"] = soc
        outputs["P_chargeable"] = self.outputs.P_chargeable
        outputs["P_dischargeable"] = self.outputs.P_dischargeable

    def simulate(
        self,
        storage_dispatch_commands: list,
        time_step_duration: list,
        control_variable: str,
        sim_start_index: int = 0,
    ):
        """Run the PySAM BatteryStateful model over a control window.

        Applies a sequence of dispatch commands (positive = discharge, negative = charge)
        one timestep at a time. Each command is clipped to allowable instantaneous
        charge / discharge limits derived from:
          1. Rated power (config.max_charge_rate)
          2. PySAM internal estimates (P_chargeable / P_dischargeable)
          3. Remaining energy headroom vs. SOC bounds

        The method updates internal rolling arrays in self.outputs in-place using
        sim_start_index as an offset (enabling sliding / receding horizon logic).

        The simulate method is much of what would normally be in the compute() method
        of a component, but is separated into its own function here to allow the dispatch()
        method to manage calls to the performance model.

        Args:
            storage_dispatch_commands : Sequence[float]
                Commanded power per timestep (kW). Negative = charge, positive = discharge.
                Length should be = config.n_control_window.
            time_step_duration : float | Sequence[float]
                Timestep duration in hours. Scalar applied uniformly or sequence matching
                len(storage_dispatch_commands).
            control_variable : str
                PySAM control input to set each step ("input_power" or "input_current").
            sim_start_index : int, optional
                Starting index for writing into persistent output arrays (default 0).

        Returns:
            tuple[np.ndarray, np.ndarray]
                (battery_power_kW, soc_percent)
                battery_power_kW : array of PySAM P values (kW) per timestep
                                    (positive = discharge, negative = charge).
                soc_percent      : array of SOC values (%) per timestep.

        Notes:
            - SOC bounds may still be exceeded slightly due to PySAM internal dynamics.
            - self.outputs.stateful_attributes are updated only if the attribute exists
            in StatePack or StateCell.
            - self.outputs.component_attributes (e.g., unmet_demand) are not modified here;
            they are populated in compute(), unless an external dispatcher manages them.
        """

        # Loop through the provided input power/current (decided by control_variable)
        self.system_model.value("dt_hr", time_step_duration)

        # initialize outputs
        storage_power_out_timesteps = np.zeros(self.config.n_control_window)
        soc_timesteps = np.zeros(self.config.n_control_window)

        # get constant battery parameters needed during all time steps
        soc_max = self.system_model.value("maximum_SOC") / 100.0
        soc_min = self.system_model.value("minimum_SOC") / 100.0

        for t, dispatch_command_t in enumerate(storage_dispatch_commands):
            # get storage SOC at time t
            soc = self.system_model.value("SOC") / 100.0

            # manually adjust the dispatch command based on SOC
            ## for when battery is withing set bounds
            # according to specs
            max_chargeable_0 = self.config.max_charge_rate
            # according to simulation
            max_chargeable_1 = np.maximum(0, -self.system_model.value("P_chargeable"))
            # according to soc
            max_chargeable_2 = np.maximum(
                0, (soc_max - soc) * self.config.max_capacity / self.dt_hr
            )
            # compare all versions of max_chargeable
            max_chargeable = np.min([max_chargeable_0, max_chargeable_1, max_chargeable_2])

            # according to specs
            max_dischargeable_0 = self.config.max_charge_rate
            # according to simulation
            max_dischargeable_1 = np.maximum(0, self.system_model.value("P_dischargeable"))
            # according to soc
            max_dischargeable_2 = np.maximum(
                0, (soc - soc_min) * self.config.max_capacity / self.dt_hr
            )
            # compare all versions of max_dischargeable
            max_dischargeable = np.min(
                [max_dischargeable_0, max_dischargeable_1, max_dischargeable_2]
            )

            if dispatch_command_t < -max_chargeable:
                dispatch_command_t = -max_chargeable
            if dispatch_command_t > max_dischargeable:
                dispatch_command_t = max_dischargeable

            # if battery soc is outside the set bounds, discharge battery down to set bounds
            if (soc > soc_max) and dispatch_command_t < 0:  # and (dispatch_command_t <= 0):
                dispatch_command_t = 0.0

            # Set the input variable to the desired value
            self.system_model.value(control_variable, dispatch_command_t)

            # Simulate the PySAM BatteryStateful model
            self.system_model.execute(0)

            # save outputs
            storage_power_out_timesteps[t] = self.system_model.value("P")
            soc_timesteps[t] = self.system_model.value("SOC")

            # Store outputs based on the outputs defined in `BatteryOutputs` above. The values are
            # scraped from the PySAM model modules `StatePack` and `StateCell`.
            for attr in self.outputs.stateful_attributes:
                if hasattr(self.system_model.StatePack, attr) or hasattr(
                    self.system_model.StateCell, attr
                ):
                    getattr(self.outputs, attr)[sim_start_index + t] = self.system_model.value(attr)

            for attr in self.outputs.component_attributes:
                getattr(self.outputs, attr)[sim_start_index + t] = getattr(self, attr)

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


def dummy_function():
    # this function is required for initializing the pyomo control input and nothing else
    pass
