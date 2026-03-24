import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, range_val, range_val_or_none
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class StoragePerformanceModelConfig(BaseConfig):
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
        max_capacity (float):
            Maximum storage energy capacity in commodity_amount_units.
            Must be greater than zero.
        max_charge_rate (float):
            Rated commodity capacity of the storage  in commodity_rate_units.
            Must be greater than zero.
        min_soc_fraction (float):
            Minimum allowable state of charge as a fraction (0 to 1).
        max_soc_fraction (float):
            Maximum allowable state of charge as a fraction (0 to 1).
        init_soc_fraction (float):
            Initial state of charge as a fraction (0 to 1).
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
    demand_profile: int | float | list = field()

    max_capacity: float = field(validator=gt_zero)
    max_charge_rate: float = field(validator=gt_zero)

    min_soc_fraction: float = field(validator=range_val(0, 1))
    max_soc_fraction: float = field(validator=range_val(0, 1))
    init_soc_fraction: float = field(validator=range_val(0, 1))

    commodity_amount_units: str = field(default=None)
    max_discharge_rate: float | None = field(default=None)
    charge_equals_discharge: bool = field(default=True)

    charge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    discharge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    round_trip_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))

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
            self.round_trip_efficiency = None
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


class StoragePerformanceModel(PerformanceModelBaseClass):
    """OpenMDAO component for a storage component.

    Attributes:
        config (StoragePerformanceModelConfig):
            Configuration parameters for the storage performance model.
        current_soc (float): soc at the start of each interval that the simulate()
            method is called
        dt_hr (float): timestep in hours.

    Inputs:
        max_charge_rate (float):
            storage charge rate in commodity_rate_units
        storage_capacity (float):
            Total energy storage capacity in commodity_amount_units
        commodity_demand (ndarray):
            Commodity demand time series (commodity_rate_units).
        commodity_in (ndarray):
            Commanded input commodity (commodity_rate_units), typically from dispatch.

    Outputs:
        unmet_demand_out (ndarray):
            Remaining unmet demand after discharge in commodity_rate_units.
        unused_commodity_out (ndarray):
            Unused energy not absorbed by the storage in commodity_rate_units.
        commodity_out (ndarray):
            Dispatched commodity to meet demand in commodity_rate_units, including commodity from
            commodity_in that was never used to charge the storage and
            storage_commodity_discharge.
        SOC (ndarray):
            storage state of charge (%).
        storage_commodity_discharge (ndarray):
            commodity output from the storage model in commodity_rate_units.

    Methods:
        setup():
            Defines model inputs, outputs, configuration, and connections
            to plant-level dispatch (if applicable).
        compute(inputs, outputs, discrete_inputs, discrete_outputs):
            Runs the storage model for a simulation timestep,
            updating outputs such as SOC, charge/discharge limits, unmet
            demand, and unused commodities.
        simulate(commodity_in, commodity_demand, time_step_duration, control_variable,
            sim_start_index=0):
            Simulates the storage behavior across timesteps using input commodity as control.
            This method is similar to what is
            provided in typical compute methods in H2Integrate for running models, but
            needs to be a separate method here to allow the dispatch function to call
            and manage the performance model.


    Notes:
        - Default timestep is 1 hour (``dt=1.0``).
        - State of charge (SOC) bounds are set using the configuration's
          ``min_soc_fraction`` and ``max_soc_fraction``.
        - If a Pyomo dispatch solver is provided, the storage will simulate
          dispatch decisions using solver inputs.
    """

    def setup(self):
        """Set up the storage performance model in OpenMDAO.

        Initializes the configuration and defines inputs/outputs for OpenMDAO.
        If dispatch connections are specified, it also sets up a discrete
        input for Pyomo solver integration.
        """
        self.config = StoragePerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        self.commodity = self.config.commodity
        self.commodity_rate_units = self.config.commodity_rate_units
        self.commodity_amount_units = self.config.commodity_amount_units
        super().setup()

        self.add_input(
            f"{self.commodity}_demand",
            val=self.config.demand_profile,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"{self.commodity} demand",
        )
        self.add_input(
            f"{self.commodity}_in",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"{self.commodity} in",
        )

        # Input design parameters
        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=self.config.commodity_rate_units,
            desc="Storage charge/discharge rate",
        )
        if not self.config.charge_equals_discharge:
            self.add_input(
                "max_discharge_rate",
                val=self.config.max_discharge_rate,
                units=self.config.commodity_rate_units,
                desc="Storage discharge rate",
            )

        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=self.commodity_amount_units,
            desc="Storage capacity",
        )

        # Output design info
        self.add_output(
            "storage_duration",
            val=self.config.max_capacity / self.config.max_charge_rate,
            units=f"({self.commodity_amount_units})/({self.commodity_rate_units})",
            desc="Estimated storage duration based on max capacity and discharge rate",
        )

        # Output profiles
        self.add_output(
            f"unmet_{self.commodity}_demand_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Unmet {self.commodity} demand",
        )

        self.add_output(
            f"unused_{self.commodity}_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Unused generated commodity",
        )

        self.add_output(
            "SOC",
            val=0.0,
            shape=self.n_timesteps,
            units="percent",
            desc="State of charge of storage",
        )

        self.add_output(
            f"storage_{self.commodity}_discharge",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"{self.commodity} output from storage only",
        )

        self.add_output(
            f"storage_{self.commodity}_charge",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"{self.commodity} input to storage only",
        )

        self.add_output(
            f"storage_{self.commodity}_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"{self.commodity} input and output from storage",
        )

        self.dt_hr = int(self.options["plant_config"]["plant"]["simulation"]["dt"]) / (
            60**2
        )  # convert from seconds to hours

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
                    self.add_discrete_input("pyomo_dispatch_solver", val=dummy_function)
                    # set the using feedback control variable to True
                    using_feedback_control = True
                    break
        if not using_feedback_control:
            # using an open-loop storage controller
            self.add_input(
                f"{self.commodity}_set_point",
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_rate_units,
            )

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """Run the storage model.

        Configures the storage stateful model parameters (SOC limits, timestep,
        thermal properties, etc.), executes the simulation, and stores the
        results in OpenMDAO outputs.

        Args:
            inputs (dict):
                Continuous input values (e.g., commodity_in, commodity_demand).
            outputs (dict):
                Dictionary where model outputs (SOC, unmet demand, etc.)
                are written.
            discrete_inputs (dict):
                Discrete inputs such as control mode or Pyomo solver.
            discrete_outputs (dict):
                Discrete outputs (unused in this component).
        """
        # Size the storage based on inputs -> method brought from HOPP
        if self.config.charge_equals_discharge:
            max_discharge_rate = inputs["max_charge_rate"][0]
        else:
            max_discharge_rate = inputs["max_discharge_rate"][0]

        self.current_soc = self.config.init_soc_fraction

        if "pyomo_dispatch_solver" in discrete_inputs:
            # Simulate the storage with provided dispatch inputs
            dispatch = discrete_inputs["pyomo_dispatch_solver"]
            # kwargs are tech-specific inputs to the simulate() method
            kwargs = {
                "charge_rate": inputs["max_charge_rate"][0],
                "discharge_rate": max_discharge_rate,
                "storage_capacity": inputs["storage_capacity"][0],
            }

            storage_commodity_out, soc = dispatch(self.simulate, kwargs, inputs)

        else:
            # Simulate the storage with provided inputs using dispatch commands from
            # an open-loop controller. The commodity_set_point should come from an
            # open-loop controller. commodity_set_point is negative when commanding
            # storage to charge and positive when commanding storage to discharge

            storage_commodity_out, soc = self.simulate(
                storage_dispatch_commands=inputs[f"{self.commodity}_set_point"],
                charge_rate=inputs["max_charge_rate"][0],
                discharge_rate=max_discharge_rate,
                storage_capacity=inputs["storage_capacity"][0],
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

        outputs[f"storage_{self.commodity}_charge"] = np.where(
            storage_commodity_out < 0, storage_commodity_out, 0
        )
        outputs[f"storage_{self.commodity}_discharge"] = np.where(
            storage_commodity_out > 0, storage_commodity_out, 0
        )

        if max_discharge_rate > 0:
            outputs["storage_duration"] = inputs["storage_capacity"][0] / max_discharge_rate
        else:
            outputs["storage_duration"] = 0.0

        outputs[f"unmet_{self.commodity}_demand_out"] = unmet_demand
        outputs[f"unused_{self.commodity}_out"] = unused_commodity
        outputs[f"storage_{self.commodity}_out"] = storage_commodity_out

        outputs[f"{self.commodity}_out"] = total_commodity_out
        outputs["SOC"] = soc

        # Set the rated commodity production from the discharge rate
        outputs[f"rated_{self.commodity}_production"] = max_discharge_rate

        # Calculate the total and annual commodity produced
        outputs[f"total_{self.commodity}_produced"] = outputs[f"{self.commodity}_out"].sum() * (
            self.dt / 3600
        )
        outputs[f"annual_{self.commodity}_produced"] = outputs[
            f"total_{self.commodity}_produced"
        ] * (1 / self.fraction_of_year_simulated)

        # Calculate the maximum theoretical commodity production over the simulation
        rated_production = (
            outputs[f"rated_{self.commodity}_production"] * self.n_timesteps * (self.dt / 3600)
        )

        if rated_production <= 0:
            outputs["capacity_factor"] = 0.0
        else:
            outputs["capacity_factor"] = outputs[f"total_{self.commodity}_produced"] / (
                rated_production
            )

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
                # Discharge efficiency losses occur as energy leaves storage.
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


def dummy_function():
    # this function is required for initializing the pyomo control input and nothing else
    pass
