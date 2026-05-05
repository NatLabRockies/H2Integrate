import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


@define(kw_only=True)
class ProfitMaximizationControlConfig(BaseConfig):
    commodity_sell_price: float = field(default=0.0)


class ProfitMaximizationControl(SystemLevelControlBase):
    """Profit-maximizing system-level controller.

    Dispatches technologies only when the commodity sell price exceeds
    the marginal cost of production:

    1. Curtailable techs run at rated capacity (zero marginal cost,
       always profitable to produce).
    2. Storage absorbs surplus / provides deficit.
    3. Dispatchable techs are dispatched in merit order (cheapest first),
       but **only if** their marginal cost is below the sell price.
       Demand may go unmet if dispatch is unprofitable.

    Configuration:
        ``plant_config["system_level_control"]["commodity_sell_price"]``
        must be set ($/(commodity_rate_unit*h), e.g. $/kWh).

    Each dispatchable technology must have a ``marginal_cost`` input
    representing its variable cost per unit of production.
    """

    def setup(self):
        super().setup()

        config = ProfitMaximizationControlConfig.from_dict(
            self.options["plant_config"]["system_level_control"]["control_parameters"]
        )

        # Commodity sell price — user-set in config, can be scalar or time-varying
        self.add_input(
            "commodity_sell_price",
            val=config.commodity_sell_price,
            shape=self.n_timesteps,
            units=f"USD/({self.commodity_units}*h)",
            desc=f"Sell price per unit of {self.commodity}",
        )

        # Add marginal cost inputs for dispatchable techs
        self.dispatchable_marginal_cost_names = []
        for tech_name in self.dispatchable_techs:
            mc_name = f"{tech_name}_marginal_cost"
            self.add_input(
                mc_name,
                val=0.0,
                units=f"USD/({self.commodity_units}*h)",
                desc=f"Marginal cost of {self.commodity} from {tech_name}",
            )
            self.dispatchable_marginal_cost_names.append(mc_name)

    def compute(self, inputs, outputs):
        demand = inputs[self.demand_input_name].copy()
        sell_price = inputs["commodity_sell_price"]  # shape (n_timesteps,)

        # 1. Curtailable techs: full production (always profitable)
        demand = self._subtract_curtailable(inputs, outputs, demand)

        # 2. Storage dispatch
        demand = self._dispatch_storage(inputs, outputs, demand)

        # 3. Profit-driven merit-order dispatch
        remaining = np.maximum(demand, 0.0)

        marginal_costs = np.array([inputs[mc][0] for mc in self.dispatchable_marginal_cost_names])
        dispatch_order = np.argsort(marginal_costs)

        # Initialize all dispatchable set_points to zero
        for set_point_name in self.dispatchable_set_point_names:
            outputs[set_point_name] = np.zeros(self.n_timesteps)

        # Dispatch only where profitable (element-wise comparison)
        for idx in dispatch_order:
            mc = marginal_costs[idx]
            profitable = mc < sell_price  # boolean mask per timestep

            set_point_name = self.dispatchable_set_point_names[idx]
            rated_name = self.dispatchable_rated_names[idx]
            rated = inputs[rated_name]

            dispatch = np.where(profitable, np.minimum(remaining, rated), 0.0)
            outputs[set_point_name] = dispatch
            remaining -= dispatch
