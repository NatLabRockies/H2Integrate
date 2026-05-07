import numpy as np

from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


class CostMinimizationControl(SystemLevelControlBase):
    """Cost-minimizing system-level controller.

    Meets demand at minimum variable cost using merit-order dispatch:

    1. Curtailable techs run at rated capacity (assuming zero marginal cost).
    2. Storage absorbs surplus / provides deficit.
    3. Dispatchable techs are dispatched in ascending marginal-cost order,
       each up to its rated capacity, until remaining demand is met.

    Marginal costs are configured via ``cost_per_tech`` in the
    ``system_level_control`` section of ``plant_config``.  Each
    dispatchable technology's entry can be:

    - A numeric value ($/commodity_unit, e.g. 0.05 for $0.05/kWh)
    - ``"buy_price"`` - use the technology's purchase price
    - ``"VarOpEx"``   - derive from VarOpEx / total production
    """

    def setup(self):
        super().setup()

        # Set up marginal cost inputs based on cost_per_tech config
        self._setup_marginal_costs()

    def compute(self, inputs, outputs):
        demand = inputs[self.demand_input_name].copy()

        # 1. Curtailable techs: full production
        demand = self._subtract_curtailable(inputs, outputs, demand)

        # 2. Storage dispatch
        demand = self._dispatch_storage(inputs, outputs, demand)

        # 3. Merit-order dispatch: cheapest dispatchable first
        remaining = np.maximum(demand, 0.0)

        marginal_costs = self._compute_marginal_costs(inputs)

        # Merit order: sort by mean marginal cost (cheapest first)
        mean_costs = np.array([mc.mean() for mc in marginal_costs])
        dispatch_order = np.argsort(mean_costs)

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
