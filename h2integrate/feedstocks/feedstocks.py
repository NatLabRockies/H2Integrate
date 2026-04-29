import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class FeedstockPerformanceConfig(BaseConfig):
    """Config class for feedstock.

    Attributes:
        commodity (str): name of the feedstock commodity
        commodity_rate_units (str): feedstock usage rate units (such as "galUS/h", "kg/h" or "kW")
        rated_capacity (float):  The rated capacity of the feedstock in `commodity_rate_units`.
            This is used to size the feedstock supply to meet the plant's needs.
    """

    commodity: str = field()
    commodity_rate_units: str = field()
    rated_capacity: float = field()


class FeedstockPerformanceModel(om.ExplicitComponent):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = FeedstockPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )
        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input(
            f"{self.config.commodity}_capacity",
            val=self.config.rated_capacity,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"{self.config.commodity}_out",
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
        )

    def compute(self, inputs, outputs):
        # Generate feedstock array operating at full capacity for the full year
        outputs[f"{self.config.commodity}_out"] = np.full(
            self.n_timesteps, inputs[f"{self.config.commodity}_capacity"][0]
        )


@define(kw_only=True)
class FeedstockCostConfig(CostModelBaseConfig):
    """Config class for feedstock.

    Attributes:
        commodity (str): name of the feedstock commodity
        commodity_rate_units (str): feedstock usage rate units (such as "galUS/h", "kg/h" or "kW")
        price (scalar or list):  The cost of the feedstock in USD/`commodity_amount_units`.
            If scalar, cost is assumed to be constant for each timestep and each year.
            If list, then it can be the cost per timestep of the simulation
        cost_year (int): dollar-year for costs.
        annual_cost (float, optional): fixed cost associated with the feedstock in USD/year
        start_up_cost (float, optional): one-time capital cost associated with the feedstock in USD.
        commodity_amount_units (str | None, optional): the amount units of the commodity (i.e.,
            "galUS", "kg" or "kW*h"). If None, will be set as `commodity_rate_units*h`
    """

    commodity: str = field()
    commodity_rate_units: str = field()
    price: int | float | list = field()
    annual_cost: float = field(default=0.0)
    start_up_cost: float = field(default=0.0)
    commodity_amount_units: str | None = field(default=None)

    def __attrs_post_init__(self):
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"


class FeedstockCostModel(CostModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = FeedstockCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        self.n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        # Set cost outputs
        super().setup()

        self.add_input(
            f"{self.config.commodity}_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
            desc=f"Consumption profile of {self.config.commodity}",
        )
        self.add_input(
            f"{self.config.commodity}_out",
            val=0,
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
        )

        self.add_input(
            "price",
            val=self.config.price,
            units=f"USD/({self.config.commodity_amount_units})",
            desc=f"Price profile of {self.config.commodity}",
        )

        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        hours_per_year = 8760
        hours_simulated = (self.dt / 3600) * self.n_timesteps
        self.fraction_of_year_simulated = hours_simulated / hours_per_year
        # since feedstocks are consumed, some outputs are appended
        # with 'consumed' rather than 'produced'

        self.add_output(
            f"total_{self.config.commodity}_consumed",
            val=0.0,
            units=self.config.commodity_amount_units,
        )

        self.add_output(
            f"annual_{self.config.commodity}_consumed",
            val=0.0,
            shape=self.plant_life,
            units=f"({self.config.commodity_amount_units})/year",
        )

        # Capacity factor is feedstock_consumed/max_feedstock_available
        self.add_output(
            "capacity_factor",
            val=0.0,
            shape=self.plant_life,
            units="unitless",
            desc="Capacity factor",
        )

        # The should be equal to the commodity_capacity input of the FeedstockPerformanceModel
        self.add_output(
            f"rated_{self.config.commodity}_production",
            val=0,
            units=self.config.commodity_rate_units,
        )

        # lifetime estimate of item replacements, represented as a fraction of the capacity.
        self.add_output("replacement_schedule", val=0.0, shape=plant_life, units="unitless")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Capacity factor is the total amount consumed / the total amount available
        outputs["capacity_factor"] = (
            inputs[f"{self.config.commodity}_consumed"].sum()
            / inputs[f"{self.config.commodity}_out"].sum()
        )

        # Sum the amount consumed
        outputs[f"total_{self.config.commodity}_consumed"] = inputs[
            f"{self.config.commodity}_consumed"
        ].sum() * (self.dt / 3600)

        # Estimate annual consumption based on consumption over the simulation
        # NOTE: once we standardize feedstock consumption outputs in models, this should
        # be updated to handle consumption that varies over years of operation
        outputs[f"annual_{self.config.commodity}_consumed"] = outputs[
            f"total_{self.config.commodity}_consumed"
        ] * (1 / self.fraction_of_year_simulated)

        outputs[f"rated_{self.config.commodity}_production"] = inputs[
            f"{self.config.commodity}_out"
        ].max()

        # Calculate costs
        price = inputs["price"]
        hourly_consumption = inputs[f"{self.config.commodity}_consumed"]
        cost_per_year = sum(price * hourly_consumption)

        outputs["CapEx"] = self.config.start_up_cost
        outputs["OpEx"] = self.config.annual_cost
        outputs["VarOpEx"] = cost_per_year
