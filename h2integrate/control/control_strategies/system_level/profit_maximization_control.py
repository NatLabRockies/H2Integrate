from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


@define(kw_only=True)
class ProfitMaximizationControlConfig(BaseConfig):
    commodity_sell_price: float = field(default=0.0)
    cost_per_tech: dict = field(default={})
    conversion_parameters: dict = field(default={})


class ProfitMaximizationControl(SystemLevelControlBase):
    """Profit-maximizing system-level controller.

    Dispatches technologies only when the commodity sell price exceeds
    the marginal cost of production:

    1. Fixed techs always produce (cannot be controlled).
    2. Flexible techs run at rated capacity (zero marginal cost,
       always profitable to produce).
    3. Storage absorbs surplus / provides deficit.
    4. Dispatchable techs are dispatched in merit order (cheapest first),
       but **only if** their marginal cost is below the sell price.
       Demand may go unmet if dispatch is unprofitable.

    Configuration:
        ``plant_config["system_level_control"]["control_parameters"]["commodity_sell_price"]``
        must be set as either a numeric value (``$/(commodity_rate_unit*h)``,
        e.g. ``$/kWh``) or the name of a finance group (e.g. ``"profast_npv"``)
        whose ``model_inputs.commodity_sell_price`` will be used.

    Marginal costs are configured via ``cost_per_tech`` in the
    ``system_level_control["control_parameters"]`` section of ``plant_config``.  Each
    dispatchable technology's entry can be:

    - A numeric value (``$/(commodity_rate_unit*h)``, e.g. ``0.05`` for
      ``$0.05/kWh``) used directly as a constant marginal cost.
    - ``"buy_price"`` — use the technology's own purchase price input
      (e.g. ``electricity_buy_price`` for a Grid tech, ``price`` for a
      Feedstock tech). The default is read from the tech's cost config
      and may be overridden at runtime via ``prob.set_val()``.
    - ``"VarOpEx"`` — derive the marginal cost from the technology's own
      ``VarOpEx`` output divided by its annualized total production.
    - ``"feedstock"`` — sum the ``VarOpEx`` of all feedstock technologies
      that are upstream of the dispatchable tech in
      ``technology_interconnections`` (using graph ancestors, so feedstocks
      behind intermediate components like combiners are included), and
      divide by the dispatchable tech's annualized total production.
    """

    def _resolve_sell_price(self, config):
        """Resolve commodity_sell_price from config.

        If the value is a string, look it up from
        ``finance_parameters.finance_groups.<name>.model_inputs.commodity_sell_price``.
        Otherwise return it as-is (numeric).
        """
        raw = config.commodity_sell_price
        if isinstance(raw, str):
            finance_groups = (
                self.options["plant_config"].get("finance_parameters", {}).get("finance_groups", {})
            )
            group = finance_groups.get(raw)
            if group is None:
                raise ValueError(
                    f"commodity_sell_price references finance group '{raw}', "
                    f"but it was not found in finance_parameters.finance_groups. "
                    f"Available groups: {list(finance_groups.keys())}"
                )
            price = group.get("model_inputs", {}).get("commodity_sell_price", None)
            if price is None:
                raise ValueError(
                    f"Finance group '{raw}' does not contain model_inputs.commodity_sell_price."
                )
            return price
        return raw

    def setup(self):
        super().setup()

        config = ProfitMaximizationControlConfig.from_dict(
            self.options["plant_config"]["system_level_control"]["control_parameters"]
        )

        # Commodity sell price - user-set in config, can be scalar or time-varying
        # Accepts a numeric value or the name of a finance group to look up
        commodity_sell_price = self._resolve_sell_price(config)
        self.add_input(
            "commodity_sell_price",
            val=commodity_sell_price,
            shape=self.n_timesteps,
            units=f"USD/({self.commodity_rate_units}*h)",
            desc=f"Sell price per unit of {self.commodity}",
        )

        # Set up marginal cost inputs based on cost_per_tech config
        self._setup_marginal_costs()

    def compute(self, inputs, outputs):
        self._run_dispatch(inputs, outputs)

    def _dispatch_dispatchables(self, commodity, remaining_demand, inputs, outputs):
        """Merit-order dispatch, profit-gated for the primary demand commodity.

        The demand commodity is dispatched only at timesteps where a
        technology's marginal cost is below the sell price. Upstream (derived)
        commodities are dispatched at minimum cost to supply the profitable
        primary production, since the profitability decision has already been
        made at the demand-commodity level.
        """
        if commodity == self.commodity:
            sell_price = inputs["commodity_sell_price"]
            return self._merit_order_dispatch(
                commodity, remaining_demand, inputs, outputs, sell_price=sell_price
            )
        return self._merit_order_dispatch(commodity, remaining_demand, inputs, outputs)
