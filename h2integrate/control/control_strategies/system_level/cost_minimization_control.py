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
        self._run_dispatch(inputs, outputs)

    def _dispatch_dispatchables(self, commodity, remaining_demand, inputs, outputs):
        """Merit-order dispatch: cheapest dispatchables first, up to rated capacity."""
        return self._merit_order_dispatch(commodity, remaining_demand, inputs, outputs)
