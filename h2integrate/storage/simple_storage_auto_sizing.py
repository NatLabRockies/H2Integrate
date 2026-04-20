import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import range_val_or_none
from h2integrate.storage.storage_baseclass import (
    StoragePerformanceBase,
    StoragePerformanceBaseConfig,
)


@define(kw_only=True)
class StorageSizingModelConfig(StoragePerformanceBaseConfig):
    """Configuration class for the StorageAutoSizingModel.

    Attributes:
        commodity (str): name of commodity
        commodity_rate_units (str): Units of the commodity (e.g., kW or kg/h).
        min_soc_fraction (float): Minimum allowable state of charge as a fraction (0 to 1).
        max_soc_fraction (float): Maximum allowable state of charge as a fraction (0 to 1).
        set_demand_as_avg_commodity_in (bool): If True, assume the demand is
            equal to the mean input commodity. If False, uses the demand input.
        demand_profile (int | float | list, optional): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
            Only used if `set_demand_as_avg_commodity_in` is False. Defaults to 0.
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
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., kW*h or kg). If not provided, defaults to commodity_rate_units*h.
    """

    commodity: str = field(converter=(str.strip, str.lower))
    commodity_rate_units: str = field(converter=str.strip)

    # TODO: add in logic for having different discharge rate
    # charge_equals_discharge: bool = field(default=True)
    set_demand_as_avg_commodity_in: bool = field()
    demand_profile: int | float | list = field(default=0.0)

    charge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    discharge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    round_trip_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))

    commodity_amount_units: str = field(default=None)

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

        # Set the default commodity_amount_units as the commodity_rate_units*h
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"

        # Check if the user provided a non-zero demand profile
        user_input_dmd = True if np.sum(self.demand_profile) > 0 else False

        # Check that the demand profile is zero if set_demand_as_avg_commodity_in is True
        if self.set_demand_as_avg_commodity_in and user_input_dmd:
            # If using the average commodity in as the demand,
            # warn users if they input the demand profile
            msg = (
                "A non-zero demand profile was provided but set_demand_as_avg_commodity_in is True."
                " The provided demand profile will not be used, the demand profile will be "
                f"calculated as the mean of ``{self.commodity}_in``. "
            )
            raise ValueError(msg)


class StorageAutoSizingModel(StoragePerformanceBase):
    """Performance model that calculates the storage charge rate and capacity needed
    to either:

    1. supply the commodity at a constant rate based on the commodity production profile or
    2. try to meet the commodity demand with the given commodity production profile.

    Then simulates performance of a basic storage component using the charge rate and
    capacity calculated.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = StorageSizingModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        self.commodity = self.config.commodity
        self.commodity_rate_units = self.config.commodity_rate_units
        self.commodity_amount_units = self.config.commodity_amount_units

        super().setup()

        # Capacity outputs
        self.add_output(
            "storage_capacity",
            val=0.0,
            shape=1,
            units=self.commodity_amount_units,
        )

        self.add_output(
            "max_charge_rate",
            val=0.0,
            shape=1,
            units=self.commodity_rate_units,
        )

        self.add_output(
            "max_discharge_rate",
            val=0.0,
            shape=1,
            units=self.commodity_rate_units,
        )

        # Check if we need to have an input for demand
        # If using the actual demand profile and using
        # open-loop control, add demand as an input
        if not self.config.set_demand_as_avg_commodity_in and not self.using_feedback_control:
            self.add_input(
                f"{self.commodity}_demand",
                val=self.config.demand_profile,
                shape=self.n_timesteps,
                units=self.commodity_rate_units,
                desc=f"{self.commodity} demand profile",
            )

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """
        Part 0: get demand profile based on user input parameters:

        1) Estimate the demand profile from either the input `commodity_demand` or assume
            the demand is the average of the `commodity_in` profile

        Part 1: calculate the storage sizes (charge rate, discharge rate, and capacity)
        needed to meet the demand. The steps to do this are:

        1) Calculate the max charge and discharge rate as the maximum of the `commodity_in`
            profile and oversize to account for charge/discharge efficiencies.
        2) Estimate the storage SOC (in `commodity_amount_units`). The SOC increases when
            charging and decreases when discharging. If `commodity_set_point` is input,
            calculate the storage SOC as the cumulative summation of the negative of
            `commodity_set_point` input (`commodity_set_point` input is
            negative when charging and positive when discharging).
            Otherwise, calculate the storage SOC as the cumulative summation of
            `commodity_in - demand`.
        3) If needed, adjust the SOC profile from Step 2 so that the minimum SOC is positive
        4) Calculate the usable storage capacity as the difference between the
            maximum SOC and minimum SOC from Steps 2 and 3.
        5) Calculate the rated storage capacity as the usable storage capacity
            (calculated in Step 4) divided by
            `config.max_soc_fraction - config.min_soc_fraction`

        Part 2: Simulate the performance of that storage model. The steps of this are:

        1) Estimate the starting SOC (as a fraction) at the start of the simulation.
            Take the first value in the SOC profile (in `commodity_amount_units`)
            and divide by the storage capacity
        2) Make an input dictionary containing the calculated demand profile,
            storage capacity, and storage fill rate, and run the storage performance.
        3) Calculate the outputs
        """

        # Part 0: get demand profile based on user input parameters
        # 1. Calculate the demand profile
        if self.config.set_demand_as_avg_commodity_in:
            if dict(inputs.items()).get(f"{self.commodity}_demand", np.array([0])).sum() > 0:
                msg = (
                    "A non-zero demand profile was input when set_demand_as_avg_commodity_in is "
                    "True. When set_demand_as_avg_commodity_in is True, the input demand profile "
                    f"cannot be used. Please ensure that ``{self.config.commodity}_in`` is zero or "
                    "set set_demand_as_avg_commodity_in as False."
                )
                raise ValueError(msg)

            commodity_demand = np.mean(inputs[f"{self.commodity}_in"]) * np.ones(self.n_timesteps)

        else:
            commodity_demand = inputs[f"{self.commodity}_demand"]

        # Part 1: Auto-size the storage to meet the demand
        # 1. Auto-size the fill rate as the max of the input commodity
        storage_max_fill_rate = np.max(inputs[f"{self.commodity}_in"])
        # Auto-size the empty rate as the max of the input commodity
        storage_max_empty_rate = np.max(inputs[f"{self.commodity}_in"])

        # Auto-size the storage capacity to meet the demand as much as possible
        # 2. Estimate the storage SOC in `commodity_amount_units`
        # NOTE: commodity_storage_soc is just an absolute value and is not a percentage.
        if f"{self.commodity}_set_point" in inputs:
            # `{self.commodity}_set_point` is negative when charging and positive when
            # discharging, the negative of `{self.commodity}_set_point` can be used to
            # estimate the SOC (which increases when charging and decreases when discharging)
            commodity_storage_soc = np.cumsum(-1 * inputs[f"{self.commodity}_set_point"])
        else:
            # estimate the SOC (which increases when charging and decreases when discharging)
            # based on the demand profile and the input commodity
            commodity_storage_soc = np.cumsum(
                inputs[f"{self.config.commodity}_in"] - commodity_demand
            )

        # 3. If needed, adjust the SOC profile from Step 2 so that the minimum SOC is positive
        minimum_soc = np.min(commodity_storage_soc)

        # Adjust soc so it's not negative.
        if minimum_soc < 0:
            commodity_storage_soc = commodity_storage_soc + np.abs(minimum_soc)

        # 4. Calculate the maximum usable storage capacity needed to meet the demand
        max_usable_storage_capacity = np.max(commodity_storage_soc) - np.min(commodity_storage_soc)

        # 5. Calculate the storage capacity to account for SOC limits
        rated_storage_capacity = max_usable_storage_capacity / (
            self.config.max_soc_fraction - self.config.min_soc_fraction
        )

        # Part 2: Simulate the storage performance based on the sizes calculated
        # Estimate the initial SOC

        # 1. Set the starting SOC (as a fraction) at the start of the simulation.
        self.current_soc = np.max(
            [self.config.min_soc_fraction, commodity_storage_soc[0] / rated_storage_capacity]
        )

        # Output the calculated storage sizes (charge rate and capacity)
        outputs["max_charge_rate"] = storage_max_fill_rate
        outputs["max_discharge_rate"] = storage_max_empty_rate
        outputs["storage_capacity"] = rated_storage_capacity

        # 2. Make dictionary of inputs containing information to pass to the controller
        # (such as demand profile, charge rate, and storage capacity)
        inputs_adjusted = dict(inputs.items())
        if self.config.set_demand_as_avg_commodity_in:
            inputs_adjusted[f"{self.commodity}_demand"] = commodity_demand

        if "pyomo_dispatch_solver" in discrete_inputs:
            inputs_adjusted["storage_capacity"] = np.array([rated_storage_capacity])
            inputs_adjusted["max_charge_rate"] = np.array([storage_max_fill_rate])

        # 3. Simulate the storage performance and calculate outputs
        outputs = self.run_storage(
            storage_max_fill_rate,
            storage_max_empty_rate,
            rated_storage_capacity,
            inputs_adjusted,
            outputs,
            discrete_inputs,
        )
