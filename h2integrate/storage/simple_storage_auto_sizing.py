from copy import deepcopy

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class StorageSizingModelConfig(BaseConfig):
    """Configuration class for the StorageAutoSizingModel.

    Attributes:
        commodity_name (str, optional): Name of the commodity being controlled (e.g., "hydrogen").
            Defaults to "hydrogen"
        commodity_units (str, optional): Units of the commodity (e.g., "kg/h"). Defaults to "kg/h"
        demand_profile (scalar or list): The demand values for each time step (in the same units
            as `commodity_units`) or a scalar for a constant demand.
    """

    commodity_name: str = field(default="hydrogen")
    commodity_units: str = field(default="kg/h")  # TODO: update to commodity_rate_units
    demand_profile: int | float | list = field(default=0.0)


class StorageAutoSizingModel(PerformanceModelBaseClass):
    """Performance model that calculates the storage charge rate and capacity needed
    to either:

    1. supply the comodity at a constant rate based on the commodity production profile or
    2. try to meet the commodity demand with the given commodity production profile.

    Inputs:
        self.commodity_in (float): Input commodity flow timeseries (e.g., hydrogen production).
            - Units: Defined in `commodity_units` (e.g., "kg/h").
        self.commodity_demand_profile (float): Demand profile of commodity.
            - Units: Defined in `commodity_units` (e.g., "kg/h").

    Outputs:
        max_capacity (float): Maximum storage capacity of the commodity.
            - Units: in non-rate units, e.g., "kg" if `commodity_units` is "kg/h"
        max_charge_rate (float): Maximum rate at which the commodity can be charged
            - Units: Defined in `commodity_units` (e.g., "kg/h").
    """

    # def initialize(self):
    #     self.options.declare("driver_config", types=dict)
    #     self.options.declare("plant_config", types=dict)
    #     self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = StorageSizingModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        self.commodity = self.config.commodity_name
        self.commodity_rate_units = self.config.commodity_units
        self.commodity_amount_units = f"({self.commodity_rate_units})*h"

        super().setup()

        self.add_input(
            f"{self.commodity}_demand_profile",
            units=f"{self.config.commodity_units}",
            val=self.config.demand_profile,
            shape=self.n_timesteps,
            desc=f"{self.commodity} demand profile timeseries",
        )

        self.add_input(
            f"{self.commodity}_in",
            shape_by_conn=True,
            units=f"{self.config.commodity_units}",
            desc=f"{self.commodity} input timeseries from production to storage",
        )

        self.add_input(
            f"{self.commodity}_set_point",
            shape_by_conn=True,
            units=f"{self.config.commodity_units}",
            desc=f"{self.commodity} input timeseries from production to storage",
        )

        self.add_output(
            "max_capacity",
            val=0.0,
            shape=1,
            units=f"({self.config.commodity_units})*h",
        )

        self.add_output(
            "max_charge_rate",
            val=0.0,
            shape=1,
            units=f"{self.config.commodity_units}",
        )

    def compute(self, inputs, outputs):
        storage_max_fill_rate = np.max(inputs[f"{self.commodity}_in"])

        ########### get storage size ###########
        if np.sum(inputs[f"{self.commodity}_demand_profile"]) > 0:
            commodity_demand = inputs[f"{self.commodity}_demand_profile"]
        else:
            commodity_demand = np.mean(inputs[f"{self.commodity}_in"]) * np.ones(
                self.n_timesteps
            )  # TODO: update demand based on end-use needs

        commodity_production = inputs[f"{self.commodity}_set_point"]

        # TODO: SOC is just an absolute value and is not a percentage. Ideally would calculate as shortfall in future.
        commodity_storage_soc = []
        for j in range(len(commodity_production)):
            if j == 0:
                commodity_storage_soc.append(commodity_production[j] - commodity_demand[j])
            else:
                commodity_storage_soc.append(
                    commodity_storage_soc[j - 1] + commodity_production[j] - commodity_demand[j]
                )

        minimum_soc = np.min(commodity_storage_soc)

        # adjust soc so it's not negative.
        if minimum_soc < 0:
            commodity_storage_soc = [x + np.abs(minimum_soc) for x in commodity_storage_soc]

        commodity_storage_capacity_kg = np.max(commodity_storage_soc) - np.min(
            commodity_storage_soc
        )

        discharge_storage = np.zeros(self.n_timesteps)
        charge_storage = np.zeros(self.n_timesteps)
        soc = deepcopy(commodity_storage_soc[0])
        output_array = np.zeros(self.n_timesteps)
        for t, demand_t in enumerate(commodity_demand):
            input_flow = commodity_production[t]
            available_charge = float(commodity_storage_capacity_kg - soc)
            available_discharge = float(soc)

            if demand_t > input_flow:
                # Discharge storage to meet demand.
                discharge_needed = demand_t - input_flow
                discharge = min(discharge_needed, available_discharge, storage_max_fill_rate)
                soc -= discharge

                discharge_storage[t] = discharge
                output_array[t] = input_flow + discharge

            else:
                # Charge storage with unused input
                unused_input = input_flow - demand_t
                charge = min(unused_input, available_charge, storage_max_fill_rate)
                soc += charge

                charge_storage[t] = charge
                output_array[t] = demand_t

        outputs["max_charge_rate"] = storage_max_fill_rate
        outputs["max_capacity"] = commodity_storage_capacity_kg

        outputs[f"{self.commodity}_out"] = output_array

        outputs[f"rated_{self.commodity}_production"] = storage_max_fill_rate
        outputs[f"total_{self.commodity}_produced"] = outputs[f"{self.commodity}_out"].sum()
        outputs[f"annual_{self.commodity}_produced"] = outputs[
            f"total_{self.commodity}_produced"
        ] * (1 / self.fraction_of_year_simulated)

        max_production = storage_max_fill_rate * self.n_timesteps * (self.dt / 3600)

        outputs["capacity_factor"] = outputs[f"total_{self.commodity}_produced"] / max_production
