import numpy as np
import openmdao.api as om
import numpy_financial as npf


class AdjustedCapexOpexComp(om.ExplicitComponent):
    """
    OpenMDAO component to adjust CapEx and OpEx values for multiple technologies to a target
    dollar year using inflation.

    This component takes in capital expenditures (CapEx), operational expenditures (OpEx),
    and their associated cost years for each technology, and adjusts them to a specified target
    dollar year using a given inflation rate. The adjusted values are output for each technology,
    along with the total adjusted CapEx and OpEx across all technologies.

    Attributes:
        inflation_rate (float): The annual inflation rate used for cost adjustment.
        target_dollar_year (int): The year to which all costs are adjusted.

    Inputs:
        capex_{tech} (float, USD): Capital expenditure for each technology.
        opex_{tech} (float, USD/year): Operational expenditure for each technology.
        cost_year_{tech} (int): Dollar year for the costs of each technology.

    Outputs:
        capex_adjusted_{tech} (float, USD): CapEx for each technology adjusted to the
            target dollar year.
        opex_adjusted_{tech} (float, USD/year): OpEx for each technology adjusted to the
            target dollar year.
        total_capex_adjusted (float, USD): Total adjusted CapEx across all technologies.
        total_opex_adjusted (float, USD/year): Total adjusted OpEx across all technologies.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("tech_configs", types=dict)
        self.options.declare("plant_config", types=dict)

    def setup(self):
        tech_configs = self.options["tech_configs"]
        plant_config = self.options["plant_config"]
        self.inflation_rate = plant_config["finance_parameters"]["cost_adjustment_parameters"][
            "cost_year_adjustment_inflation"
        ]
        self.target_dollar_year = plant_config["finance_parameters"]["cost_adjustment_parameters"][
            "target_dollar_year"
        ]
        plant_life = self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        for tech in tech_configs:
            self.add_input(f"capex_{tech}", val=0.0, units="USD")
            self.add_input(f"opex_{tech}", val=0.0, units="USD/year")
            self.add_input(f"varopex_{tech}", val=0.0, shape=plant_life, units="USD/year")

            self.add_discrete_input(f"cost_year_{tech}", val=0, desc="Dollar year for costs")

            self.add_output(f"capex_adjusted_{tech}", val=0.0, units="USD")
            self.add_output(f"opex_adjusted_{tech}", val=0.0, units="USD/year")
            self.add_output(f"varopex_adjusted_{tech}", val=0.0, shape=plant_life, units="USD/year")

        self.add_output("total_capex_adjusted", val=0.0, units="USD")
        self.add_output("total_opex_adjusted", val=0.0, units="USD/year")
        self.add_output("total_varopex_adjusted", val=0.0, shape=plant_life, units="USD/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        total_capex_adjusted = 0.0
        total_opex_adjusted = 0.0
        total_varopex_adjusted = np.zeros(self.plant_life)
        for tech in self.options["tech_configs"]:
            capex = inputs[f"capex_{tech}"][0]
            opex = inputs[f"opex_{tech}"][0]
            varopex = inputs[f"varopex_{tech}"]
            cost_year = int(discrete_inputs[f"cost_year_{tech}"])
            periods = self.target_dollar_year - cost_year
            adjusted_capex = -npf.fv(self.inflation_rate, periods, 0.0, capex)
            adjusted_opex = -npf.fv(self.inflation_rate, periods, 0.0, opex)
            adjusted_varopex = -npf.fv(self.inflation_rate, periods, 0.0, varopex)
            outputs[f"capex_adjusted_{tech}"] = adjusted_capex
            outputs[f"opex_adjusted_{tech}"] = adjusted_opex
            outputs[f"varopex_adjusted_{tech}"] = adjusted_varopex
            total_capex_adjusted += adjusted_capex
            total_opex_adjusted += adjusted_opex
            total_varopex_adjusted += adjusted_varopex

        outputs["total_capex_adjusted"] = total_capex_adjusted
        outputs["total_opex_adjusted"] = total_opex_adjusted
        outputs["total_varopex_adjusted"] = total_varopex_adjusted
