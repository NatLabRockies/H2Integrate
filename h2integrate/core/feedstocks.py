import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class FeedstockPerformanceConfig(BaseConfig):
    """Config class for feedstock.

    Attributes:
        name (str): feedstock name
        units (str): feedstock usage units (such as "galUS" or "kg")
        rated_capacity (float):  The rated capacity of the feedstock in `units`/hour.
            This is used to size the feedstock supply to meet the plant's needs.
    """

    feedstock_type: str = field()
    units: str = field()
    rated_capacity: float = field()


class FeedstockPerformanceModel(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = FeedstockPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        feedstock_type = self.config.feedstock_type

        self.add_output(f"{feedstock_type}_out", shape=n_timesteps, units=self.config.units)

    def compute(self, inputs, outputs):
        feedstock_type = self.config.feedstock_type
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        # Generate feedstock array operating at full capacity for the full year
        outputs[f"{feedstock_type}_out"] = np.full(n_timesteps, self.config.rated_capacity)


@define(kw_only=True)
class FeedstockCostConfig(CostModelBaseConfig):
    """Config class for feedstock.

    Attributes:
        name (str): feedstock name
        units (str): feedstock usage units (such as "galUS" or "kg")
        price (scalar or list):  The cost of the feedstock in USD/`units`).
            If scalar, cost is assumed to be constant for each timestep and each year.
            If list, then it can be the cost per timestep of the simulation

        annual_cost (float, optional): fixed cost associated with the feedstock in USD/year
        start_up_cost (float, optional): one-time capital cost associated with the feedstock in USD.
        cost_year (int): dollar-year for costs.
    """

    feedstock_type: str = field()
    units: str = field()
    price: int | float | list = field()
    annual_cost: float = field(default=0.0)
    start_up_cost: float = field(default=0.0)


class FeedstockCostModel(CostModelBaseClass):
    def setup(self):
        self.config = FeedstockCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        super().setup()

        feedstock_type = self.config.feedstock_type
        self.add_input(
            f"{feedstock_type}_consumed",
            val=0.0,
            shape=int(n_timesteps),
            units=self.config.units,
            desc=f"Consumption profile of {feedstock_type}",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        feedstock_type = self.config.feedstock_type
        price = self.config.price
        hourly_consumption = inputs[f"{feedstock_type}_consumed"]
        cost_per_year = sum(price * hourly_consumption)

        outputs["CapEx"] = self.config.start_up_cost
        outputs["OpEx"] = self.config.annual_cost
        outputs["VarOpEx"] = cost_per_year
