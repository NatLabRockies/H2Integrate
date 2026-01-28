from attrs import field, define
from openmdao.utils import units

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import contains, gte_zero, range_val
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class ATBBatteryCostConfig(CostModelBaseConfig):
    """Configuration class for the ATBBatteryCostModel with costs based on storage
    capacity and charge rate. More information on ATB methodology and representative
    battery technologies can be found
    `here <https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage>`_
    Reference cost values can be found on the `Utility-Scale Battery Storage`,
    `Commercial Battery Storage`, and `Residential Battery Storage` sheets of the
    `NREL ATB workbook <https://atb.nrel.gov/electricity/2024/data>`_.

    Attributes:
        energy_capex (float|int): battery energy capital cost in $/kWh
        power_capex (float|int): battery power capital cost in $/kW
        opex_fraction (float): annual operating cost as a fraction of the total system cost.
        cost_year (int): dollar year corresponding to input costs
        max_capacity (float): Maximum storage capacity of the battery (in non-rate units,
            e.g., "kW*h" if `commodity_units` is "kW").
        max_charge_rate (float): Maximum rate at which the battery can be charged (in units
            per time step, e.g., "kW/time step").
        commodity_units (str): Units of the electricity resource used to define the
            max_capacity and max_charge_rate. Must have a base of Watts ('W').
    """

    energy_capex: float | int = field(validator=gte_zero)
    power_capex: float | int = field(validator=gte_zero)
    opex_fraction: float = field(validator=range_val(0, 1))
    max_capacity: float = field()
    max_charge_rate: float = field()
    commodity_units: str = field(validator=contains(["W", "kW", "MW", "GW", "TW"]))


class ATBBatteryCostModel(CostModelBaseClass):
    """This cost model is based on the equations in the "Utility-Scale Battery Storage"
    sheet in the ATB 2024 workbook.

    - Cell E29 has the equation for CapEx. Also found in the cells for the CapEx section.
    - Cell G121 (all the cells in the Fixed Operation and Maintenance Expenses
        section) include the equation to calculate fixed o&m costs.

    Total_CapEx = Energy_CapEx * Storage_Hours + Power_CapEx

    - Total_CapEx: Total System Cost (USD/kW)
    - Storage_Hours: Storage Duration (hr)
    - Energy_CapEx: Battery Energy Cost (USD/kWh)
    - Power_CapEx: Battery Power Cost (USD/kW)

    """

    def setup(self):
        self.config = ATBBatteryCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"), strict=False
        )

        super().setup()

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=f"{self.config.commodity_units}",
            desc="Battery charge/discharge rate",
        )
        self.add_input(
            "max_capacity",
            val=self.config.max_capacity,
            units=f"{self.config.commodity_units}*h",
            desc="Battery storage capacity",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        storage_duration_hrs = 0.0

        # convert the input capacity to units of kW*h
        max_capacity_kWh = units.convert_units(
            inputs["max_capacity"], f"{self.config.commodity_units}*h", "kW*h"
        )

        # convert the input charge rate to units of kW
        max_charge_rate_kW = units.convert_units(
            inputs["max_charge_rate"], self.config.commodity_units, "kW"
        )

        if max_charge_rate_kW > 0:
            storage_duration_hrs = max_capacity_kWh / max_charge_rate_kW
        if max_charge_rate_kW < 0:
            msg = (
                f"max_charge_rate cannot be less than zero and has value of "
                f"{max_charge_rate_kW} kW"
            )
            raise UserWarning(msg)
        # CapEx equation from Cell E29
        total_system_cost = (
            storage_duration_hrs * self.config.energy_capex
        ) + self.config.power_capex
        capex = total_system_cost * max_charge_rate_kW
        # OpEx equation from cells in the Fixed Operation and Maintenance Expenses section
        opex = self.config.opex_fraction * capex
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
