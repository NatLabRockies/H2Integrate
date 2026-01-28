import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


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
    commodity_units: str = field(default="kg/h")
    demand_profile: int | float | list = field(default=0.0)


class StorageAutoSizingModel(om.ExplicitComponent):
    """Performance model that calculates the storage charge rate and capacity needed
    to either:

    1. supply the comodity at a constant rate based on the commodity production profile or
    2. try to meet the commodity demand with the given commodity production profile.

    Inputs:
        {commodity_name}_in (float): Input commodity flow timeseries (e.g., hydrogen production).
            - Units: Defined in `commodity_units` (e.g., "kg/h").
        {commodity_name}_demand_profile (float): Demand profile of commodity.
            - Units: Defined in `commodity_units` (e.g., "kg/h").

    Outputs:
        max_capacity (float): Maximum storage capacity of the commodity.
            - Units: in non-rate units, e.g., "kg" if `commodity_units` is "kg/h"
        max_charge_rate (float): Maximum rate at which the commodity can be charged
            - Units: Defined in `commodity_units` (e.g., "kg/h").
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = StorageSizingModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )

        super().setup()

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        commodity_name = self.config.commodity_name

        self.add_input(
            f"{commodity_name}_demand_profile",
            units=f"{self.config.commodity_units}",
            val=self.config.demand_profile,
            shape=n_timesteps,
            desc=f"{commodity_name} demand profile timeseries",
        )

        self.add_input(
            f"{commodity_name}_in",
            shape_by_conn=True,
            units=f"{self.config.commodity_units}",
            desc=f"{commodity_name} input timeseries from production to storage",
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
        commodity_name = self.config.commodity_name
        storage_max_fill_rate = np.max(inputs[f"{commodity_name}_in"])

        ########### get storage size ###########
        if np.sum(inputs[f"{commodity_name}_demand_profile"]) > 0:
            commodity_demand = inputs[f"{commodity_name}_demand_profile"]
        else:
            commodity_demand = np.mean(
                inputs[f"{commodity_name}_in"]
            )  # TODO: update demand based on end-use needs

        commodity_production = inputs[f"{commodity_name}_in"]

        # TODO: SOC is just an absolute value and is not a percentage. Ideally would calculate as shortfall in future.
        commodity_storage_soc = []
        for j in range(len(commodity_production)):
            if j == 0:
                commodity_storage_soc.append(commodity_production[j] - commodity_demand)
            else:
                commodity_storage_soc.append(
                    commodity_storage_soc[j - 1] + commodity_production[j] - commodity_demand
                )

        minimum_soc = np.min(commodity_storage_soc)

        # adjust soc so it's not negative.
        if minimum_soc < 0:
            commodity_storage_soc = [x + np.abs(minimum_soc) for x in commodity_storage_soc]

        commodity_storage_capacity_kg = np.max(commodity_storage_soc) - np.min(
            commodity_storage_soc
        )

        outputs["max_charge_rate"] = storage_max_fill_rate
        outputs["max_capacity"] = commodity_storage_capacity_kg
