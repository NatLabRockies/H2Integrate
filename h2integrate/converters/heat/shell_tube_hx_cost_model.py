from attrs import field, define

from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define()
class ShellTubeHXCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for the ShellTubeHXCostModel.

    Args:
        Q_ref (float|int): Reference heat transfer rate for cost scaling in W
        C_ref (float|int): Reference capital cost for cost scaling in USD
        exp_Q (float|int): Exponent for heat transfer cost scaling
    """

    Q_ref: float | int = field(validator=gt_zero)
    C_ref: float | int = field(validator=gt_zero)
    exp_Q: float | int = field(validator=gt_zero)


class ShellTubeHXCostModel(CostModelBaseClass):
    """_summary_
    This is a very simple placeholder cost model:

    - Reference: 240,000 USD for a 1 MW HX with U ~ 1000 W/m²-K
    - Scale CapEx ~ (Q / Q_ref)^0.8
    - OpEx = 4% of CapEx per year
    """

    def setup(self):
        print(self.options["tech_config"])
        self.config = ShellTubeHXCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input("Q_total_W", val=0.0, units="W", desc="Total heat transfer rate")
        self.add_input(
            "Q_ref",
            val=self.config.Q_ref,
            units="W",
            desc="Reference heat transfer rate for cost scaling",
        )
        self.add_input(
            "C_ref",
            val=self.config.C_ref,
            units="USD",
            desc="Reference capital cost for cost scaling",
        )
        self.add_input(
            "exp_Q",
            val=self.config.exp_Q,
            units="unitless",
            desc="Exponent for heat transfer cost scaling",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        Q_total_W = inputs["Q_total_W"][0]
        Q_ref = inputs["Q_ref"][0]
        C_ref = inputs["C_ref"][0]
        exp_Q = inputs["exp_Q"][0]

        scale_Q = (Q_total_W / Q_ref) ** exp_Q if Q_total_W > 0 else 0.0
        capex = C_ref * scale_Q
        opex = 0.04 * capex

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
