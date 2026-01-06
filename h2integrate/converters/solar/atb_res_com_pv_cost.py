from attrs import field, define

from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class ATBResComPVCostModelConfig(CostModelBaseConfig):
    """Configuration class for the ATBResComPVCostModel with costs based on DC capacity.
    Recommended to use with commercial or residential PV models. More information on
    ATB methodology and representative PV technologies can be found
    `here for commercial PV <https://atb.nrel.gov/electricity/2024/commercial_pv>`_ and
    `here for residential PV <https://atb.nrel.gov/electricity/2024/residential_pv>`_.
    Reference cost values can be found on the `Solar - PV Dist. Comm` or
    `Solar - PV Dist. Res` sheets of the
    `NREL ATB workbook <https://atb.nrel.gov/electricity/2024/data>`_.

    Attributes:
        capex_per_kWdc (float|int): capital cost of solar-PV system in $/kW-DC
        opex_per_kWdc_per_year (float|int): annual operating cost of solar-PV
            system in $/kW-DC/year
        pv_capacity_kWdc (float): capacity of solar-PV system in kW-DC
        cost_year (int): dollar year corresponding to input costs
    """

    capex_per_kWdc: float | int = field(validator=gt_zero)
    opex_per_kWdc_per_year: float | int = field(validator=gt_zero)
    pv_capacity_kWdc: float = field()


class ATBResComPVCostModel(CostModelBaseClass):
    def setup(self):
        self.config = ATBResComPVCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input(
            "system_capacity_DC",
            val=self.config.pv_capacity_kWdc,
            units="kW",
            desc="PV rated capacity in DC",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capacity = inputs["system_capacity_DC"][0]
        capex = self.config.capex_per_kWdc * capacity
        opex = self.config.opex_per_kWdc_per_year * capacity
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
