import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import range_val
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class StoragePerformanceBaseConfig(BaseConfig):
    """
    Configuration class for the StoragePerformanceBase model.

     Attributes:
        min_soc_fraction (float): Minimum allowable state of charge as a fraction (0 to 1).
        max_soc_fraction (float): Maximum allowable state of charge as a fraction (0 to 1).
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
    """

    # Below are used in all storage models
    min_soc_fraction: float = field(validator=range_val(0, 1))
    max_soc_fraction: float = field(validator=range_val(0, 1))
    demand_profile: int | float | list = field()


class StoragePerformanceBase(PerformanceModelBaseClass):
    """
    Baseclass for storage performance models

    Attributes:
        config (StoragePerformanceModelConfig):
            Configuration parameters for the storage performance model.
        current_soc (float): soc at the start of each interval that the simulate()
            method is called
        dt_hr (float): timestep in hours.


    Notes:
        - Default timestep is 1 hour (``dt=3600.0``).
        - State of charge (SOC) bounds are set using the configuration's
          ``min_soc_fraction`` and ``max_soc_fraction``.
        - If a Pyomo dispatch solver is provided, the storage will simulate
          dispatch decisions using solver inputs.
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def setup(self):
        """Set up the storage performance model in OpenMDAO.

        Initializes the configuration and defines inputs/outputs for OpenMDAO.
        If dispatch connections are specified, it also sets up a discrete
        input for Pyomo solver integration.
        """

        # Below should be done in models that inherit it
        # self.commodity = self.config.commodity
        # self.commodity_rate_units = self.config.commodity_rate_units
        # self.commodity_amount_units = self.config.commodity_amount_units

        # Initialize standard performance model outputs
        super().setup()

        commodity = self.commodity
        commodity_rate_units = self.commodity_rate_units
        commodity_amount_units = self.commodity_amount_units
        n_timesteps = self.n_timesteps

        # Input timeseries
        self.add_input(
            f"{commodity}_demand",
            val=self.config.demand_profile,
            shape=n_timesteps,
            units=commodity_rate_units,
            desc=f"{commodity} demand profile",
        )

        self.add_input(
            f"{commodity}_in",
            val=0,
            shape=n_timesteps,
            units=commodity_rate_units,
            desc=f"{commodity} input",
        )

        # Input storage design parameters
        if hasattr(self.config, "max_charge_rate"):
            self.add_input(
                "max_charge_rate",
                val=self.config.max_charge_rate,
                units=commodity_rate_units,
                desc="Storage charge rate",
            )

        if hasattr(self.config, "max_capacity"):
            self.add_input(
                "storage_capacity",
                val=self.config.max_capacity,
                units=commodity_amount_units,
                desc="Storage capacity",
            )

        if not getattr(self.config, "charge_equals_discharge", True):
            # add max_discharge_rate if discharge rate != charge rate
            self.add_input(
                "max_discharge_rate",
                val=self.config.max_discharge_rate,
                units=commodity_rate_units,
                desc="Storage discharge rate",
            )

        # Storage design outputs:
        default_storage_duration = 0.0
        if hasattr(self.config, "max_charge_rate") and hasattr(self.config, "max_capacity"):
            default_storage_duration = self.config.max_capacity / self.config.max_charge_rate

        self.add_output(
            "storage_duration",
            val=default_storage_duration,
            units=f"({commodity_amount_units})/({commodity_rate_units})",
            desc="Storage duration capacity",
        )

        # Storage performance outputs
        self.add_output(
            "SOC",
            val=0.0,
            shape=n_timesteps,
            units="percent",
            desc="State of charge of storage",
        )

        self.add_output(
            f"storage_{commodity}_discharge",
            val=0.0,
            shape=n_timesteps,
            units=commodity_rate_units,
            desc=f"{commodity} output from storage only",
        )

        self.add_output(
            f"storage_{commodity}_charge",
            val=0.0,
            shape=n_timesteps,
            units=commodity_rate_units,
            desc=f"{commodity} input to storage only",
        )

        self.add_output(
            f"storage_{commodity}_out",
            val=0.0,
            shape=n_timesteps,
            units=commodity_rate_units,
            desc=f"{commodity} input and output from storage",
        )

        self.add_output(
            f"unmet_{commodity}_demand_out",
            val=0.0,
            shape=n_timesteps,
            units=commodity_rate_units,
            desc=f"Unmet {commodity} demand",
        )

        self.add_output(
            f"unused_{commodity}_out",
            val=0.0,
            shape=n_timesteps,
            units=commodity_rate_units,
            desc="Unused generated commodity",
        )

        # create a variable to determine whether we are using feedback control
        # for this technology
        using_feedback_control = False
        # create inputs for pyomo control model
        if "tech_to_dispatch_connections" in self.options["plant_config"]:
            # get technology group name
            # TODO: The split below seems brittle
            self.tech_group_name = self.pathname.split(".")
            for _source_tech, intended_dispatch_tech in self.options["plant_config"][
                "tech_to_dispatch_connections"
            ]:
                if any(intended_dispatch_tech in name for name in self.tech_group_name):
                    self.add_discrete_input("pyomo_dispatch_solver", val=lambda: None)
                    # set the using feedback control variable to True
                    using_feedback_control = True
                    break
        if not using_feedback_control:
            # using an open-loop storage controller
            self.add_input(
                f"{commodity}_set_point",
                val=0.0,
                shape=n_timesteps,
                units=commodity_rate_units,
            )
        # convert from seconds to hours
        self.dt_hr = int(self.options["plant_config"]["plant"]["simulation"]["dt"]) / (
            3600
        )  # convert from seconds to hours

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """Run the storage model.

        Configures the storage stateful model parameters (SOC limits, timestep,
        thermal properties, etc.), executes the simulation, and stores the
        results in OpenMDAO outputs.

        Args:
            inputs (dict): Continuous input values (e.g., commodity_in, commodity_demand).
            outputs (dict): Dictionary where model outputs (SOC, unmet demand, etc.)
                are written.
            discrete_inputs (dict): Discrete inputs such as control mode or Pyomo solver.
            discrete_outputs (dict): Discrete outputs (unused in this component).
        """
        # Below is an example of what the compute method would look like in the
        # StoragePerformanceModel
        # Do whatever pre-calculations are necessary, then run storage
        # self.current_soc = self.config.init_soc_fraction

        # charge_rate = inputs["max_charge_rate"][0]
        # if "max_discharge_rate" in inputs:
        #     discharge_rate = inputs["max_discharge_rate"][0]
        # else:
        #     discharge_rate = inputs["max_charge_rate"][0]
        # storage_capacity = inputs["storage_capacity"][0]
        # outputs = self.run_storage(
        #     charge_rate, discharge_rate, storage_capacity, inputs, outputs, discrete_inputs
        # )
        raise NotImplementedError("This method should be implemented in a subclass")

    def run_storage(
        self, charge_rate, discharge_rate, storage_capacity, inputs, outputs, discrete_inputs
    ):
        """Run the storage performance model and calculate the outputs. This method should
        be called in the `compute()` method of a subclass.

        Example:
            >>> # In the `compute()` method:
            >>> self.current_soc = self.config.init_soc_fraction
            >>> charge_rate = inputs["max_charge_rate"][0]
            >>> discharge_rate = inputs["max_discharge_rate"][0]
            >>> storage_capacity = inputs["storage_capacity"]
            >>> outputs = self.run_storage(
            ... charge_rate, discharge_rate, storage_capacity, inputs, outputs, discrete_inputs
            >>> )

        Args:
            charge_rate (float): storage charge rate in commodity_rate_units
            discharge_rate (float): storage discharge rate in commodity_rate_units
            storage_capacity (float): storage capacity in commodity_amount_units
            inputs (om.vectors.default_vector.DefaultVector | dict): OpenMDAO inputs
                to the `compute()` method. This should at least include the commodity
                demand profile and input commodity profile.
            outputs (om.vectors.default_vector.DefaultVector): OpenMDAO outputs
                from the `compute()` method
            discrete_inputs (om.core.component._DictValues, optional): OpenMDAO discrete
                inputs to the `compute()` method. This is only required if using a
                feedback control strategy and should contain the discrete input
                'pyomo_dispatch_solver'.

        Returns:
            om.vectors.default_vector.DefaultVector: calculated OpenMDAO outputs.
        """
        if "pyomo_dispatch_solver" in discrete_inputs:
            dispatch = discrete_inputs["pyomo_dispatch_solver"]
            # kwargs are tech-specific inputs to the simulate() method
            kwargs = {
                "charge_rate": charge_rate,
                "discharge_rate": discharge_rate,
                "storage_capacity": storage_capacity,
            }
            storage_commodity_out, soc = dispatch(self.simulate, kwargs, inputs)

        else:
            storage_commodity_out, soc = self.simulate(
                storage_dispatch_commands=inputs[f"{self.commodity}_set_point"],
                charge_rate=charge_rate,
                discharge_rate=discharge_rate,
                storage_capacity=storage_capacity,
            )

        # determine storage charge and discharge
        # storage_commodity_out is positive when the storage is discharged
        # and negative when the storage is charged
        storage_commodity_out = np.array(storage_commodity_out)

        # calculate combined commodity out from inflow source and storage
        # (note: storage_commodity_out is negative when charging)
        combined_commodity_out = inputs[f"{self.commodity}_in"] + storage_commodity_out

        # find the total commodity out to meet demand
        total_commodity_out = np.minimum(inputs[f"{self.commodity}_demand"], combined_commodity_out)

        # determine how much of the inflow commodity was unused
        unused_commodity = np.maximum(
            0, combined_commodity_out - inputs[f"{self.commodity}_demand"]
        )

        # determine how much demand was not met
        unmet_demand = np.maximum(0, inputs[f"{self.commodity}_demand"] - combined_commodity_out)

        # Storage design outputs
        if discharge_rate > 0:
            outputs["storage_duration"] = storage_capacity / discharge_rate
        else:
            outputs["storage_duration"] = 0

        # Storage specific timeseries outputs
        outputs[f"storage_{self.commodity}_charge"] = np.where(
            storage_commodity_out < 0, storage_commodity_out, 0
        )
        outputs[f"storage_{self.commodity}_discharge"] = np.where(
            storage_commodity_out > 0, storage_commodity_out, 0
        )
        outputs["SOC"] = soc
        outputs[f"storage_{self.commodity}_out"] = storage_commodity_out

        # System-level outputs calculated in storage
        outputs[f"unmet_{self.commodity}_demand_out"] = unmet_demand
        outputs[f"unused_{self.commodity}_out"] = unused_commodity
        outputs[f"{self.commodity}_out"] = total_commodity_out

        # Performance model outputs
        outputs[f"rated_{self.commodity}_production"] = discharge_rate
        outputs[f"total_{self.commodity}_produced"] = np.sum(total_commodity_out)
        outputs[f"annual_{self.commodity}_produced"] = outputs[
            f"total_{self.commodity}_produced"
        ] * (1 / self.fraction_of_year_simulated)

        if outputs[f"rated_{self.commodity}_production"] <= 0:
            outputs["capacity_factor"] = 0.0
        else:
            outputs["capacity_factor"] = outputs[f"total_{self.commodity}_produced"] / (
                outputs[f"rated_{self.commodity}_production"] * self.n_timesteps
            )
        return outputs

    def simulate(
        self,
        storage_dispatch_commands: list,
        charge_rate: float,
        discharge_rate: float,
        storage_capacity: float,
        sim_start_index: int = 0,
    ):
        """Run the storage model over a control window of ``n_control_window`` timesteps.

        Iterates through ``storage_dispatch_commands`` one timestep at a time.
        A negative command requests charging; a positive command requests
        discharging.  Each command is clipped to the most restrictive of three
        limits before it is applied:

        1. **SOC headroom** - the remaining capacity (charge) or remaining
           stored commodity (discharge), converted to a rate via
           ``storage_capacity / dt_hr``.
        2. **Hardware rate limit** - ``charge_rate`` or ``discharge_rate``,
           divided by the corresponding efficiency so the limit is expressed
           in pre-efficiency rate units.
        3. **Commanded magnitude** - the absolute value of the dispatch command
           itself (we never exceed what was asked for).

        After clipping, the result is scaled by the charge or discharge
        efficiency to obtain the actual commodity flow into or out of the
        storage, and the SOC is updated accordingly.

        This method is separated from ``compute()`` so the Pyomo dispatch
        controller can call it directly to evaluate candidate schedules.

        Args:
            storage_dispatch_commands (array_like[float]):
                Dispatch set-points for each timestep in ``commodity_rate_units``.
                Negative values command charging; positive values command
                discharging.  Length must equal ``config.n_control_window``.
            charge_rate (float):
                Maximum commodity input rate to storage in
                ``commodity_rate_units`` (before charge efficiency is applied).
            discharge_rate (float):
                Maximum commodity output rate from storage in
                ``commodity_rate_units`` (before discharge efficiency is applied).
            storage_capacity (float):
                Rated storage capacity in ``commodity_amount_units``.
            sim_start_index (int, optional):
                Starting index for writing into persistent output arrays.
                Defaults to 0.

        Returns:
            tuple[np.ndarray, np.ndarray]
                storage_commodity_out_timesteps :
                    Commodity flow per timestep in ``commodity_rate_units``.
                    Positive = discharge (commodity leaving storage),
                    negative = charge (commodity entering storage).
                soc_timesteps :
                    State of charge at the end of each timestep, in percent
                    (0-100).
        """

        n = len(storage_dispatch_commands)
        storage_commodity_out_timesteps = np.zeros(n)
        soc_timesteps = np.zeros(n)

        # Early return when storage cannot operate: zero capacity or both
        # charge and discharge rates are zero.
        if storage_capacity <= 0 or (charge_rate <= 0 and discharge_rate <= 0):
            soc_timesteps[:] = self.current_soc * 100.0
            return storage_commodity_out_timesteps, soc_timesteps

        # Pre-compute scalar constants to avoid repeated attribute lookups
        # and redundant divisions inside the per-timestep loop.
        charge_eff = self.config.charge_efficiency
        discharge_eff = self.config.discharge_efficiency
        soc_max = self.config.max_soc_fraction
        soc_min = self.config.min_soc_fraction

        commands = np.asarray(storage_dispatch_commands, dtype=float)
        soc = float(self.current_soc)

        for t, cmd in enumerate(commands):
            if cmd < 0.0:
                # --- Charging ---
                # headroom: how much more commodity the storage can accept,
                # expressed as a rate (commodity_rate_units).
                headroom = (soc_max - soc) * storage_capacity / self.dt_hr

                # Clip to the most restrictive limit, then apply efficiency.
                # max(0, ...) guards against negative headroom when SOC
                # slightly exceeds soc_max.
                # correct headroom to not include charge_eff.
                actual_charge = max(0.0, min(headroom / charge_eff, charge_rate, -cmd)) * charge_eff

                # Update SOC (actual_charge is in post-efficiency units)
                soc += actual_charge / storage_capacity

                # Update the amount of commodity used to charge from the input stream
                # If charge_eff<1, more commodity is pulled from the input stream than
                # the commodity that goes into the storage.
                storage_commodity_out_timesteps[t] = -actual_charge / charge_eff
            else:
                # --- Discharging ---
                # headroom: how much commodity can still be drawn before
                # hitting the minimum SOC, expressed as a rate.
                headroom = (soc - soc_min) * storage_capacity / self.dt_hr

                # Clip to the most restrictive limit without applied efficiency.
                # Efficiency losses occur as energy leaves storage.
                actual_discharge = max(
                    0.0, min(headroom, discharge_rate / discharge_eff, cmd / discharge_eff)
                )

                # Update SOC (actual_discharge is before efficiency losses are applied.)
                soc -= actual_discharge / storage_capacity

                # If discharge_eff<1, then less commodity is output from the storage
                # than the commodity discharged from storage
                storage_commodity_out_timesteps[t] = actual_discharge * discharge_eff

            soc_timesteps[t] = soc * 100.0

        # Persist the final SOC so subsequent simulate() calls (e.g. from the
        # Pyomo controller across rolling windows) start where we left off.
        self.current_soc = soc
        return storage_commodity_out_timesteps, soc_timesteps
