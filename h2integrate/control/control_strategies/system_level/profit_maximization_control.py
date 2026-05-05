import numpy as np

from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


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

    Marginal costs are configured via ``cost_per_tech`` in the
    ``system_level_control`` section of ``plant_config``.  Each
    dispatchable technology's entry can be:

    - A numeric value ($/commodity_unit, e.g. 0.05 for $0.05/kWh)
    - ``"buy_price"`` — use the technology's purchase price
    - ``"VarOpEx"``   — derive from VarOpEx / total production
    """

    def setup(self):
        super().setup()

        slc_config = self.options["plant_config"]["system_level_control"]

        # Commodity sell price — user-set in config, can be scalar or time-varying
        default_sell_price = slc_config.get("commodity_sell_price", 0.0)
        self.add_input(
            "commodity_sell_price",
            val=default_sell_price,
            shape=self.n_timesteps,
            units=f"USD/({self.commodity_units}*h)",
            desc=f"Sell price per unit of {self.commodity}",
        )

        # Set up marginal cost inputs based on cost_per_tech config
        self._setup_marginal_costs()

    def compute(self, inputs, outputs):
        demand = inputs[self.demand_input_name].copy()
        sell_price = inputs["commodity_sell_price"]  # shape (n_timesteps,)

        # 1. Curtailable techs: full production (always profitable)
        demand = self._subtract_curtailable(inputs, outputs, demand)

        # 2. Storage dispatch
        demand = self._dispatch_storage(inputs, outputs, demand)

        # 3. Profit-driven merit-order dispatch
        remaining = np.maximum(demand, 0.0)

        marginal_costs = self._compute_marginal_costs(inputs)

        # Merit order: sort by mean marginal cost (cheapest first)
        mean_costs = np.array([mc.mean() for mc in marginal_costs])
        dispatch_order = np.argsort(mean_costs)

        # Initialize all dispatchable set_points to zero
        for set_point_name in self.dispatchable_set_point_names:
            outputs[set_point_name] = np.zeros(self.n_timesteps)

        # Dispatch only where profitable (element-wise comparison)
        for idx in dispatch_order:
            mc = marginal_costs[idx]  # per-timestep array
            profitable = mc < sell_price  # boolean mask per timestep

            set_point_name = self.dispatchable_set_point_names[idx]
            rated_name = self.dispatchable_rated_names[idx]
            rated = inputs[rated_name]

            dispatch = np.where(profitable, np.minimum(remaining, rated), 0.0)
            outputs[set_point_name] = dispatch
            remaining -= dispatch
