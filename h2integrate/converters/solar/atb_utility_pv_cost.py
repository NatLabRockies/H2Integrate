from attrs import field, define

from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class ATBUtilityPVCostModelConfig(CostModelBaseConfig):
    """Configuration class for the ATBUtilityPVCostModel with costs based on AC capacity.
    Recommended to use with utility-scale PV models. More information on
    ATB methodology and representative utility-scale PV technologies can be found
    `here <https://atb.nrel.gov/electricity/2024/utility-scale_pv>`_
    Reference cost values can be found on the `Solar - Utility PV` sheet of the
    `NREL ATB workbook <https://atb.nrel.gov/electricity/2024/data>`_.

    Attributes:
        capex_per_kWac (float|int): capital cost of solar-PV system in $/kW-AC
        opex_per_kWac_per_year (float|int): annual operating cost of solar-PV
            system in $/kW-AC/year
        cost_year (int): dollar year corresponding to input costs
    """

    capex_per_kWac: float | int = field(validator=gt_zero)
    opex_per_kWac_per_year: float | int = field(validator=gt_zero)


class ATBUtilityPVCostModel(CostModelBaseClass):
    def setup(self):
        self.config = ATBUtilityPVCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input("system_capacity_AC", val=0.0, units="kW", desc="PV rated capacity in AC")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capacity = inputs["system_capacity_AC"][0]
        capex = self.config.capex_per_kWac * capacity
        opex = self.config.opex_per_kWac_per_year * capacity
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
