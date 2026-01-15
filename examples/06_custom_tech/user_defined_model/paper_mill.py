import numpy as np
import openmdao.api as om
import numpy_financial as npf
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


n_timesteps = 8760


@define(kw_only=True)
class PaperMillConfig(BaseConfig):
    electricity_usage_rate: float = field()


class PaperMillPerformance(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = PaperMillConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        self.add_input(
            "electricity_in",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Power inputted to the paper mill",
        )

        self.add_output(
            "paper",
            shape=n_timesteps,
            units="t",
            desc="Paper produced from the paper mill",
        )

    def compute(self, inputs, outputs):
        # Calculate the paper produced
        outputs["paper"] = inputs["electricity_in"] * self.config.electricity_usage_rate


@define(kw_only=True)
class PaperMillCostConfig(CostModelBaseConfig):
    cost_per_tonne: float = field()
    opex_rate: float = field()
    plant_capacity: float = field()


class PaperMillCost(CostModelBaseClass):
    def setup(self):
        self.config = PaperMillCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Calculate the cost of the paper mill
        print(self.config.cost_per_tonne, self.config.plant_capacity)
        outputs["CapEx"] = self.config.cost_per_tonne * self.config.plant_capacity
        outputs["OpEx"] = self.config.opex_rate * self.config.plant_capacity


class PaperMillFinance(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.add_input("CapEx", val=0.0, units="USD", desc="Capital expenditure")
        self.add_input("OpEx", val=0.0, units="USD/year", desc="Operational expenditure")
        self.add_input("paper", shape=n_timesteps, units="t", desc="Annual paper production")

        self.add_output(
            "LCOP",
            val=0.0,
            units="USD/t",
            desc="Levelized cost of paper production",
        )

    def compute(self, inputs, outputs):
        # Financial parameters
        project_lifetime = self.options["plant_config"]["plant"]["plant_life"]  # years
        discount_rate = self.options["tech_config"]["model_inputs"]["finance_parameters"][
            "discount_rate"
        ]  # annual discount rate

        # Calculate the annualized CapEx using the present value of an annuity formula
        annualized_CapEx = npf.pmt(discount_rate, project_lifetime, -inputs["CapEx"])

        # Total annual cost
        total_annual_cost = annualized_CapEx + inputs["OpEx"]

        # Calculate the levelized cost of paper production
        outputs["LCOP"] = total_annual_cost / np.sum(inputs["paper"])
