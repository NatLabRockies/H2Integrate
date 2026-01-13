import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class GridPerformanceModelConfig(BaseConfig):
    """Configuration for the grid performance model.

    Attributes:
        interconnection_size: Maximum power capacity for grid connection in kW
    """

    interconnection_size: float = field()  # kW


class GridPerformanceModel(om.ExplicitComponent):
    """Model a grid interconnection point.

    The grid is treated as the interconnection point itself:
    - electricity_in: Power flowing INTO the grid (selling to grid).
    - electricity_out: Power flowing OUT OF the grid (buying from grid).

    This component handles:
    - Buying electricity from the grid (electricity flows out to downstream technologies).
    - Selling electricity to the grid (electricity flows in from upstream technologies).
    - Enforcing interconnection limits on buying flows.

    The component can be instantiated multiple times in a plant to represent
    different grid connection points (for example, one for buying upstream and
    another for selling downstream).

    Inputs
        interconnection_size (float): Maximum power capacity for grid connection (kW).
        electricity_in (array): Power flowing into the grid (selling) (kW).
        electricity_demand (array): Downstream electricity demand (kW).

    Outputs
        electricity_out (array): Power flowing out of the grid (buying) (kW).
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = GridPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Interconnection size input
        self.add_input(
            "interconnection_size",
            val=self.config.interconnection_size,
            units="kW",
            desc="Maximum power capacity for grid connection",
        )

        # Electricity flowing INTO the grid (selling to grid)
        self.add_input(
            "electricity_in",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity flowing into grid interconnection point (selling to grid)",
        )

        # Electricity demand from downstream (for buying from grid)
        self.add_input(
            "electricity_demand",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity demand from downstream technologies",
        )

        # Electricity flowing OUT OF the grid (buying from grid)
        self.add_output(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity flowing out of grid interconnection point (buying from grid)",
        )

        self.add_output(
            "electricity_sold",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity sold to the grid",
        )

        self.add_output(
            "electricity_unmet_demand",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity demand that is not met",
        )

        self.add_output(
            "electricity_excess",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity that was not sold due to interconnection limits",
        )

    def compute(self, inputs, outputs):
        interconnection_size = inputs["interconnection_size"]

        # Selling: electricity flows into grid, limited by interconnection size
        electricity_sold = np.clip(inputs["electricity_in"], 0, interconnection_size)
        outputs["electricity_sold"] = electricity_sold

        # Buying: electricity flows out of grid to meet demand, limited by interconnection
        electricity_bought = np.clip(inputs["electricity_demand"], 0, interconnection_size)
        outputs["electricity_out"] = electricity_bought

        # Unmet demand if demand exceeds interconnection size
        outputs["electricity_unmet_demand"] = inputs["electricity_demand"] - electricity_bought

        # Not sold electricity if demand exceeds interconnection size
        outputs["electricity_excess"] = inputs["electricity_in"] - electricity_sold


@define(kw_only=True)
class GridCostModelConfig(CostModelBaseConfig):
    """Configuration for the grid cost model.

    Attributes:
        interconnection_size: Maximum power capacity for grid connection in kW
        interconnection_capex_per_kw: Capital cost per kW of interconnection ($/kW)
        interconnection_opex_per_kw: Annual O&M cost per kW of interconnection ($/kW/year)
        fixed_interconnection_cost: One-time fixed cost regardless of size ($)
        electricity_buy_price: Price to buy electricity from grid ($/kWh), optional
        electricity_sell_price: Price to sell electricity to grid ($/kWh), optional
    """

    interconnection_size: float = field()  # kW
    interconnection_capex_per_kw: float = field()  # $/kW
    interconnection_opex_per_kw: float = field()  # $/kW/year
    fixed_interconnection_cost: float = field()  # $
    electricity_buy_price: float | list[float] | np.ndarray | None = field(default=None)  # $/kWh
    electricity_sell_price: float | list[float] | np.ndarray | None = field(default=None)  # $/kWh


class GridCostModel(CostModelBaseClass):
    """
    An OpenMDAO component that computes costs for grid connections.

    This component handles:
    - CapEx based on interconnection size ($/kW)
    - OpEx based on interconnection size ($/kW/year)
    - Variable costs for electricity purchases (buy mode)
    - Revenue from electricity sales (sell mode)
    - Support for time-varying electricity prices

    Note: Although the electricity units are in kW and the prices are in USD/kWh,
    this model assumes that each timestep represents 1 hour.
    """

    def setup(self):
        self.config = GridCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Common input for sizing costs
        self.add_input(
            "interconnection_size",
            val=self.config.interconnection_size,
            units="kW",
            desc="Interconnection capacity for cost calculation",
        )

        # Electricity flowing OUT of grid (buying from grid)
        self.add_input(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity flowing out of grid (buying from grid)",
        )

        # Add buy price input if configured
        if self.config.electricity_buy_price is not None:
            buy_price = self.config.electricity_buy_price
            if isinstance(buy_price, (list, np.ndarray)):
                if len(buy_price) != n_timesteps:
                    raise ValueError(
                        f"electricity_buy_price length ({len(buy_price)}) "
                        f"must match n_timesteps ({n_timesteps})"
                    )
                buy_price_shape = n_timesteps

            else:
                buy_price_shape = 1

            self.add_input(
                "electricity_buy_price",
                val=self.config.electricity_buy_price,
                shape=buy_price_shape,
                units="USD/(kW*h)",
                desc="Price to buy electricity from grid",
            )

        # Electricity flowing INTO grid (selling to grid)
        self.add_input(
            "electricity_sold",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity flowing into grid (selling to grid)",
        )

        # Add sell price input if configured
        if self.config.electricity_sell_price is not None:
            sell_price = self.config.electricity_sell_price
            if isinstance(sell_price, (list, np.ndarray)):
                if len(sell_price) != n_timesteps:
                    raise ValueError(
                        f"electricity_sell_price length ({len(sell_price)}) "
                        f"must match n_timesteps ({n_timesteps})"
                    )
                sell_price_shape = n_timesteps
            else:
                sell_price_shape = 1

            self.add_input(
                "electricity_sell_price",
                val=self.config.electricity_sell_price,
                shape=sell_price_shape,
                units="USD/(kW*h)",
                desc="Price to sell electricity to grid",
            )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        interconnection_size = inputs["interconnection_size"]

        # Capital costs based on interconnection size
        capex_per_kw = self.config.interconnection_capex_per_kw
        fixed_cost = self.config.fixed_interconnection_cost
        outputs["CapEx"] = (interconnection_size * capex_per_kw) + fixed_cost

        # Fixed operating costs based on interconnection size
        opex_per_kw = self.config.interconnection_opex_per_kw
        outputs["OpEx"] = interconnection_size * opex_per_kw

        # Variable operating costs (positive cost for buying, negative for selling)
        varopex = 0.0

        # Add buying costs if buy price is configured
        # electricity_out represents power flowing OUT of grid (buying)
        if self.config.electricity_buy_price is not None:
            electricity_out = inputs["electricity_out"]
            buy_price = inputs["electricity_buy_price"]
            # Buying costs money (positive VarOpEx)
            varopex += np.sum(electricity_out * buy_price)

        # Add selling revenue if sell price is configured
        # electricity_sold represents power flowing INTO grid (selling)
        if self.config.electricity_sell_price is not None:
            sell_price = inputs["electricity_sell_price"]
            # Selling generates revenue (negative VarOpEx)
            varopex -= np.sum(inputs["electricity_sold"] * sell_price)

        outputs["VarOpEx"] = varopex
