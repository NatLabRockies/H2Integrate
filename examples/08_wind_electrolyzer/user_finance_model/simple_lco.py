import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import gt_zero, range_val


@define(kw_only=True)
class SimpleLCOFinanceConfig(BaseConfig):
    discount_rate: float = field(validator=range_val(0, 1))
    plant_life: int = field(converter=int, validator=gt_zero)


class SimpleLCOFinance(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("commodity_type", types=str)
        self.options.declare("description", types=str, default="")

    def setup(self):
        if self.options["commodity_type"] == "electricity":
            commodity_units = "kW*h/year"
            lco_units = "USD/(kW*h)"
        else:
            commodity_units = "kg/year"
            lco_units = "USD/kg"

        # Make unique names for outputs
        LCO_base_str = f"LCO{self.options['commodity_type'][0].upper()}"
        self.output_txt = (
            self.options["commodity_type"].lower()
            if self.options["description"] == ""
            else f"{self.options['commodity_type'].lower()}_{self.options['description']}"
        )
        self.LCO_str = (
            LCO_base_str
            if self.options["description"] == ""
            else f"{LCO_base_str}_{self.options['description']}"
        )

        # add inputs for commodity production and costs
        self.add_input(
            f"total_{self.options['commodity_type']}_produced",
            val=0.0,
            units=commodity_units,
        )
        tech_config = self.tech_config = self.options["tech_config"]
        for tech in tech_config:
            self.add_input(f"capex_adjusted_{tech}", val=0.0, units="USD")
            self.add_input(f"opex_adjusted_{tech}", val=0.0, units="USD/year")

        # add plant life to the input config dictionary
        finance_config = self.options["plant_config"]["finance_parameters"]["model_inputs"]
        finance_config.update({"plant_life": self.options["plant_config"]["plant"]["plant_life"]})

        # initialize config
        self.config = SimpleLCOFinanceConfig.from_dict(finance_config)

        # add outputs
        self.add_output(self.LCO_str, val=0.0, units=lco_units)
        self.add_output(f"total_capital_cost_{self.output_txt}", val=0.0, units="USD")
        self.add_output(
            f"annual_fixed_costs_{self.output_txt}",
            val=0.0,
            shape=self.config.plant_life,
            units="USD",
        )

    def compute(self, inputs, outputs):
        annual_output = float(inputs[f"total_{self.options['commodity_type']}_produced"][0])

        total_capex = 0
        total_fixed_om = 0

        for tech in self.tech_config:
            tech_model_inputs = self.tech_config[tech].get("model_inputs")
            if tech_model_inputs is None:
                continue  # Skip this tech if no model_inputs
            one_time_capital_cost = float(inputs[f"capex_adjusted_{tech}"][0])
            fixed_om_cost_per_year = float(inputs[f"opex_adjusted_{tech}"][0])

            total_capex += one_time_capital_cost
            total_fixed_om += fixed_om_cost_per_year

        # initialize outputs per year
        annual_production = np.zeros(self.config.plant_life)
        annual_OM = np.zeros(self.config.plant_life)

        for y in range(self.config.plant_life):
            denom = (1 + self.config.discount_rate) ** y
            annual_production[y] = annual_output / denom
            annual_OM[y] = total_fixed_om / denom

        lco = (total_capex + np.sum(annual_OM)) / np.sum(annual_production)

        # add outputs
        outputs[self.LCO_str] = lco
        outputs[f"total_capital_cost_{self.output_txt}"] = total_capex
        outputs[f"annual_fixed_costs_{self.output_txt}"] = annual_OM
