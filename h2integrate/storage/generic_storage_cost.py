from attrs import field, define
from openmdao.utils import units

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

    Fields include `capacity_capex`, `charge_capex`, `opex_fraction`, `max_capacity`,
    `max_charge_rate`, and `commodity_rate_units`. The `cost_year` field is inherited
    from `CostModelBaseConfig`.
    """

    capacity_capex: float | int = field(validator=gte_zero)
    charge_capex: float | int = field(validator=gte_zero)
    opex_fraction: float = field(validator=range_val(0, 1))
    max_capacity: float = field()
    max_charge_rate: float = field()
    commodity_rate_units: str = field(
        validator=contains(["W", "kW", "MW", "GW", "TW", "g/h", "kg/h", "t/h", "MMBtu/h"])
    )

    commodity_amount_units: str = field(default=None)

    def __attrs_post_init__(self):
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"


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
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        charge_units = self.config.commodity_rate_units

        capacity_units = self.config.commodity_amount_units

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=charge_units,
            desc="Storage charge/discharge rate",
        )
        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=capacity_units,
            desc="Storage storage capacity",
        )
        self.add_input(
            "capacity_capex",
            val=self.config.capacity_capex,
            units=f"USD/({capacity_units})",
            desc="Storage energy capital cost",
        )
        self.add_input(
            "charge_capex",
            val=self.config.charge_capex,
            units=f"USD/({charge_units})",
            desc="Storage power capital cost",
        )
        self.add_input(
            "opex_fraction",
            val=self.config.opex_fraction,
            units="unitless",
            desc="Annual operating cost as a fraction of total system cost",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        storage_duration_hrs = 0.0

        if inputs["max_charge_rate"] > 0:
            storage_duration_hrs = units.convert_units(
                inputs["storage_capacity"] / inputs["max_charge_rate"],
                f"({self.config.commodity_amount_units})/({self.config.commodity_rate_units})",
                "h",
            )
        if inputs["max_charge_rate"] < 0:
            msg = (
                f"max_charge_rate cannot be less than zero and has value of "
                f"{inputs['max_charge_rate']}"
            )
            raise UserWarning(msg)
        # Calculate total system cost based on capacity and charge components
        total_system_cost = (storage_duration_hrs * inputs["capacity_capex"]) + inputs[
            "charge_capex"
        ]
        capex = total_system_cost * inputs["max_charge_rate"]
        # Calculate operating expenses as a fraction of capital expenses
        opex = inputs["opex_fraction"] * capex
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
