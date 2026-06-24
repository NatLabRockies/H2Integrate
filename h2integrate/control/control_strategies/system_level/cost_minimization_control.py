import numpy as np

from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


class CostMinimizationControl(SystemLevelControlBase):
    """Cost-minimizing system-level controller.

    Meets demand at minimum variable cost using merit-order dispatch:

    1. Fixed techs always produce (cannot be controlled).
    2. Flexible techs run at rated capacity (assuming zero marginal cost).
    3. Storage absorbs surplus / provides deficit.
    4. Dispatchable techs are dispatched in ascending marginal-cost order,
       each up to its rated capacity, until remaining demand is met.

    Marginal costs are configured via ``cost_per_tech`` in the
    ``system_level_control["control_parameters"]`` section of ``plant_config``.  Each
    dispatchable technology's entry can be:

    - A numeric value (``$/(commodity_rate_unit*h)``, e.g. ``0.05`` for
      ``$0.05/kWh``) used directly as a constant marginal cost.
    - ``"buy_price"`` - use the technology's own purchase price input
      (e.g. ``electricity_buy_price`` for a Grid tech, ``price`` for a
      Feedstock tech). The default is read from the tech's cost config
      and may be overridden at runtime via ``prob.set_val()``.
    - ``"VarOpEx"`` - derive the marginal cost from the technology's own
      ``VarOpEx`` output divided by its annualized total production.
    - ``"feedstock"`` - sum the ``VarOpEx`` of all feedstock technologies
      that are upstream of the dispatchable tech in
      ``technology_interconnections`` (using graph ancestors, so feedstocks
      behind intermediate components like combiners are included), and
      divide by the dispatchable tech's annualized total production.
    """

    def setup(self):
        super().setup()

        # Set up marginal cost inputs based on cost_per_tech config
        self._setup_marginal_costs()

    def compute(self, inputs, outputs):
        demand = inputs[self.demand_input_name].copy()

        # 1. Fixed techs: always produce, subtract from demand
        for fixed_tech in self.fixed_techs:
            commodity_from_tech = self._get_commodity_for_tech(fixed_tech)
            if self.commodity in commodity_from_tech:
                demand = self._subtract_fixed(fixed_tech, demand, self.commodity, inputs)

        # 2. Flexible techs: full production
        for flexible_tech in self.flexible_techs:
            commodity_from_tech = self._get_commodity_for_tech(flexible_tech)
            if self.commodity in commodity_from_tech:
                demand = self._subtract_flexible(
                    flexible_tech, demand, self.commodity, inputs, outputs
                )

        # 3. Storage dispatch
        # number of storage components that produce the demanded commodity
        n_storage = len(
            [s for s in self.storage_techs if self.commodity in self._get_commodity_for_tech(s)]
        )
        for storage_tech in self.storage_techs:
            commodity_from_tech = self._get_commodity_for_tech(storage_tech)
            if self.commodity in commodity_from_tech:
                demand = self._dispatch_storage(
                    storage_tech, demand / n_storage, self.commodity, inputs, outputs
                )

        # 4. Merit-order dispatch: cheapest dispatchable first
        remaining = np.maximum(demand, 0.0)

        marginal_costs = self._compute_marginal_costs(inputs)

        # Merit order: sort by mean marginal cost (cheapest first)
        mean_costs = np.array([mc.mean() for mc in marginal_costs])
        dispatch_order = np.argsort(mean_costs)

        # Initialize all dispatchable set-point outputs to zero
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
