from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import contains, gte_zero, range_val
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class GenericStorageCostConfig(CostModelBaseConfig):
    """Configuration class for the GenericStorageCostModel with costs based on storage
    capacity and charge rate for any commodity.

    Note:
        This could be expanded to allow for different types of commodity units in the future.
        Currently only supports electrical, mass, and some thermal units.

    Attributes:
        capacity_capex (float|int): storage energy capital cost in $/capacity_units
        charge_capex (float|int): storage power capital cost in $/charge_units/h
        opex_fraction (float): annual operating cost as a fraction of the total system cost.
        cost_year (int): dollar year corresponding to input costs
        max_capacity (float): Maximum storage capacity (in non-rate units,
            e.g., "kW*h" if `commodity_units` is "kW").
        max_charge_rate (float): Maximum rate at which storage can be charged (in units
            per time step, e.g., "kW/time step").
        commodity_units (str): Units of the storage resource used to define the charge rate.
            max_capacity and max_charge_rate. Must have a base of Watts ('W') or grams ('g/h')
            or heat ('MMBtu/h')
    """

    capacity_capex: float | int = field(validator=gte_zero)
    charge_capex: float | int = field(validator=gte_zero)
    opex_fraction: float = field(validator=range_val(0, 1))
    max_capacity: float = field()
    max_charge_rate: float = field()
    commodity_units: str = field(
        validator=contains(["W", "kW", "MW", "GW", "TW", "g/h", "kg/h", "t/h", "MMBtu/h"])
    )


class GenericStorageCostModel(CostModelBaseClass):
    """Generic storage cost model for any commodity (electricity, hydrogen, etc.).

    This model calculates costs based on storage capacity and charge/discharge rate.

    Total_CapEx = capacity_capex * Storage_Hours + charge_capex

    - Total_CapEx: Total System Cost (USD/charge_units)
    - Storage_Hours: Storage Duration (hr)
    - capacity_capex: Storage Capacity Cost (USD/capacity_units)
    - charge_capex: Storage Charge Cost (USD/charge_units)

    """

    def setup(self):
        self.config = GenericStorageCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"), strict=False
        )

        super().setup()

        charge_units = self.config.commodity_units

        capacity_units = f"({self.config.commodity_units})*h"

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=charge_units,
            desc="Storage charge/discharge rate",
        )
        self.add_input(
            "max_capacity",
            val=self.config.max_capacity,
            units=capacity_units,
            desc="Storage storage capacity",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        storage_duration_hrs = 0.0

        if inputs["max_charge_rate"] > 0:
            storage_duration_hrs = inputs["max_capacity"] / inputs["max_charge_rate"]
        if inputs["max_charge_rate"] < 0:
            msg = (
                f"max_charge_rate cannot be less than zero and has value of "
                f"{inputs['max_charge_rate']}"
            )
            raise UserWarning(msg)
        # Calculate total system cost based on capacity and charge components
        total_system_cost = (
            storage_duration_hrs * self.config.capacity_capex
        ) + self.config.charge_capex
        capex = total_system_cost * inputs["max_charge_rate"]
        # Calculate operating expenses as a fraction of capital expenses
        opex = self.config.opex_fraction * capex
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
