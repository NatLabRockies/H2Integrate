import numpy as np

from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


class CostMinimizationControl(SystemLevelControlBase):
    """Cost-minimizing system-level controller.

    Meets demand at minimum variable cost using merit-order dispatch:

    1. Curtailable techs run at rated capacity (zero marginal cost).
    2. Storage absorbs surplus / provides deficit.
    3. Dispatchable techs are dispatched in ascending marginal-cost order,
       each up to its rated capacity, until remaining demand is met.

    Each dispatchable technology must have a ``marginal_cost`` input
    ($/commodity_rate_unit·h, e.g. $/kWh) representing its variable cost
    per unit of production.  These are connected from cost model outputs
    or set as defaults in the plant config.
    """

    def setup(self):
        super().setup()

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

        # 1. Curtailable techs: full production
        demand = self._subtract_curtailable(inputs, outputs, demand)

        # 2. Storage dispatch
        demand = self._dispatch_storage(inputs, outputs, demand)

        # 3. Merit-order dispatch: cheapest dispatchable first
        remaining = np.maximum(demand, 0.0)

        # Collect marginal costs and sort by ascending cost
        marginal_costs = np.array([inputs[mc][0] for mc in self.dispatchable_marginal_cost_names])
        dispatch_order = np.argsort(marginal_costs)

        # Initialize all dispatchable set_points to zero
        for set_point_name in self.dispatchable_set_point_names:
            outputs[set_point_name] = np.zeros(self.n_timesteps)

        # Dispatch in merit order
        for idx in dispatch_order:
            set_point_name = self.dispatchable_set_point_names[idx]
            rated_name = self.dispatchable_rated_names[idx]
            rated = inputs[rated_name]

            dispatch = np.minimum(remaining, rated)
            outputs[set_point_name] = dispatch
            remaining -= dispatch
