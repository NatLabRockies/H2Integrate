from copy import deepcopy

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class StorageSizingModelConfig(BaseConfig):
    """Configuration class for the StorageAutoSizingModel.

    Attributes:
        commodity (str, optional): Name of the commodity being controlled (e.g., "hydrogen").
            Defaults to "hydrogen"
        commodity_rate_units (str, optional): Units of the commodity (e.g., "kg/h").
            Defaults to "kg/h".
        demand_profile (scalar or list): The demand values for each time step (in the same units
            as `commodity_rate_units`) or a scalar for a constant demand.
    """

    commodity: str = field(default="hydrogen")
    commodity_rate_units: str = field(default="kg/h")  # TODO: update to commodity_rate_units
    demand_profile: int | float | list = field(default=0.0)


class StorageAutoSizingModel(PerformanceModelBaseClass):
    """Performance model that calculates the storage charge rate and capacity needed
    to either:

    1. supply the commodity at a constant rate based on the commodity production profile or
    2. try to meet the commodity demand with the given commodity production profile.

    Then simulates performance of a basic storage component using the charge rate and
    capacity calculated.

    Note: this storage performance model is intended to be used with the
    `PassThroughOpenLoopController` controller and is not compatible with the
    `DemandOpenLoopStorageController` controller.

    Inputs:
        {commodity}_in (float): Input commodity flow timeseries (e.g., hydrogen production)
            used to estimate the demand if `commodity_demand_profile` is zero.
            - Units: Defined in `commodity_rate_units` (e.g., "kg/h").
        {commodity}_set_point (float): Input commodity flow timeseries (e.g., hydrogen production)
            used as the available input commodity to meet the demand.
        {commodity}_demand_profile (float): Demand profile of commodity.
            - Units: Defined in `commodity_rate_units` (e.g., "kg/h").


    Outputs:
        max_capacity (float): Maximum storage capacity of the commodity.
            - Units: in non-rate units, e.g., "kg" if `commodity_rate_units` is "kg/h"
        max_charge_rate (float): Maximum rate at which the commodity can be charged
            - Units: Defined in `commodity_rate_units` (e.g., "kg/h").
            Assumed to also be the discharge rate.
        {commodity}_out (np.ndarray): the commodity used to meet demand from the available
            input commodity and storage component. Defined in `commodity_rate_units`.
        total_{commodity}_produced (float): sum of commodity discharged from storage over
            the simulation. Defined in `commodity_rate_units*h`
        rated_{commodity}_production (float): maximum commodity that could be discharged
            in a timestep. Defined in `commodity_rate_units`
        annual_{commodity}_produced (np.ndarray): total commodity discharged per year.
            Defined in `commodity_rate_units*h/year`
        capacity_factor (np.ndarray): ratio of commodity discharged to the maximum
            commodity that could be discharged over the simulation.
            Defined as a ratio (units of `unitless`)

    """

    def setup(self):
        self.config = StorageSizingModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        self.commodity = self.config.commodity
        self.commodity_rate_units = self.config.commodity_rate_units
        self.commodity_amount_units = f"({self.commodity_rate_units})*h"

        super().setup()

        self.add_input(
            f"{self.commodity}_demand_profile",
            units=f"{self.config.commodity_rate_units}",
            val=self.config.demand_profile,
            shape=self.n_timesteps,
            desc=f"{self.commodity} demand profile timeseries",
        )

        self.add_input(
            f"{self.commodity}_in",
            shape_by_conn=True,
            units=f"{self.config.commodity_rate_units}",
            desc=f"{self.commodity} input timeseries from production to storage",
        )

        self.add_input(
            f"{self.commodity}_set_point",
            shape_by_conn=True,
            units=f"{self.config.commodity_rate_units}",
            desc=f"{self.commodity} input set point from controller",
        )

        self.add_output(
            "max_capacity",
            val=0.0,
            shape=1,
            units=f"({self.config.commodity_rate_units})*h",
        )

        self.add_output(
            "max_charge_rate",
            val=0.0,
            shape=1,
            units=f"{self.config.commodity_rate_units}",
        )

    def compute(self, inputs, outputs):
        # Step 1: Auto-size the storage to meet the demand

        # Auto-size the fill rate as the max of the input commodity
        storage_max_fill_rate = np.max(inputs[f"{self.commodity}_in"])

        # Set the demand profile
        if np.sum(inputs[f"{self.commodity}_demand_profile"]) > 0:
            commodity_demand = inputs[f"{self.commodity}_demand_profile"]
        else:
            # If the commodity_demand_profile is zero, use the average
            # commodity_in as the demand
            commodity_demand = np.mean(inputs[f"{self.commodity}_in"]) * np.ones(
                self.n_timesteps
            )  # TODO: update demand based on end-use needs

        # The commodity_set_point is the production set by the controller
        desired_commodity_production = inputs[f"{self.commodity}_set_point"]

        # TODO: SOC is just an absolute value and is not a percentage. Ideally would calculate as shortfall in future.
        # Size the storage capacity to meet the demand as much as possible
        commodity_storage_soc = []
        for j in range(len(desired_commodity_production)):
            if j == 0:
                commodity_storage_soc.append(desired_commodity_production[j] - commodity_demand[j])
            else:
                commodity_storage_soc.append(
                    commodity_storage_soc[j - 1]
                    + desired_commodity_production[j]
                    - commodity_demand[j]
                )

        minimum_soc = np.min(commodity_storage_soc)

        # Adjust soc so it's not negative.
        if minimum_soc < 0:
            commodity_storage_soc = [x + np.abs(minimum_soc) for x in commodity_storage_soc]

        # Calculate the maximum hydrogen storage capacity needed to meet the demand
        commodity_storage_capacity_kg = np.max(commodity_storage_soc) - np.min(
            commodity_storage_soc
        )

        # Step 2: Simulate the storage performance based on the sizes calculated

        # Initialize output arrays of charge and discharge
        discharge_storage = np.zeros(self.n_timesteps)
        charge_storage = np.zeros(self.n_timesteps)
        output_array = np.zeros(self.n_timesteps)

        # Initialize state-of-charge value as the soc at t=0
        soc = deepcopy(commodity_storage_soc[0])

        # Simulate a basic storage component
        for t, demand_t in enumerate(commodity_demand):
            input_flow = desired_commodity_production[t]
            available_charge = float(commodity_storage_capacity_kg - soc)
            available_discharge = float(soc)

            # If demand is greater than the input, discharge storage
            if demand_t > input_flow:
                # Discharge storage to meet demand.
                discharge_needed = demand_t - input_flow
                discharge = min(discharge_needed, available_discharge, storage_max_fill_rate)
                # Update SOC
                soc -= discharge

                discharge_storage[t] = discharge
                output_array[t] = input_flow + discharge

            # If input is greater than the demand, charge storage
            else:
                # Charge storage with unused input
                unused_input = input_flow - demand_t
                charge = min(unused_input, available_charge, storage_max_fill_rate)
                # Update SOC
                soc += charge

                charge_storage[t] = charge
                output_array[t] = demand_t

        # Output the storage sizes (charge rate and capacity)
        outputs["max_charge_rate"] = storage_max_fill_rate
        outputs["max_capacity"] = commodity_storage_capacity_kg

        # commodity_out is the commodity_set_point - charge_storage + discharge_storage
        outputs[f"{self.commodity}_out"] = output_array

        # The rated_commodity_production is based on the discharge rate
        # (which is assumed equal to the charge rate)
        outputs[f"rated_{self.commodity}_production"] = storage_max_fill_rate

        # The total_commodity_produced is the sum of the commodity discharged from storage
        outputs[f"total_{self.commodity}_produced"] = discharge_storage.sum()
        # Adjust the total_commodity_produced to a year-long simulation
        outputs[f"annual_{self.commodity}_produced"] = outputs[
            f"total_{self.commodity}_produced"
        ] * (1 / self.fraction_of_year_simulated)

        # The maximum production is based on the charge/discharge rate
        max_production = storage_max_fill_rate * self.n_timesteps * (self.dt / 3600)

        # Capacity factor is total discharged commodity / maximum discharged commodity possible
        outputs["capacity_factor"] = outputs[f"total_{self.commodity}_produced"] / max_production
