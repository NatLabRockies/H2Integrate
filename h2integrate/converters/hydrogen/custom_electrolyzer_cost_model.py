from attrs import field, define

from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gte_zero
from h2integrate.converters.hydrogen.electrolyzer_baseclass import ElectrolyzerCostBaseClass


@define(kw_only=True)
class CustomElectrolyzerCostModelConfig(CostModelBaseConfig):
    """Configuration class for the CustomElectrolyzerCostModel.

    Attributes:
        capex_USD_per_kW (float): capital cost of electrolyzer system in USD/kW
        fixed_om_USD_per_kW_per_year (float): fixed annual operating cost of
            electrolyzer system in USD/kW/year
        cost_year (int): dollar year of capex_USD_per_kW and
            fixed_om_USD_per_kW_per_year
    """

    capex_USD_per_kW: float = field(validator=gte_zero)
    fixed_om_USD_per_kW_per_year: float = field(validator=gte_zero)


class CustomElectrolyzerCostModel(ElectrolyzerCostBaseClass):
    """
    An OpenMDAO component that computes the cost of a PEM electrolyzer.
    """

    def setup(self):
        self.config = CustomElectrolyzerCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

        self.add_input(
            "electrolyzer_size_mw",
            val=0,
            units="kW",
            desc="Size of the electrolyzer in kW",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        electrolyzer_size_kW = inputs["electrolyzer_size_mw"]
        outputs["CapEx"] = self.config.capex_USD_per_kW * electrolyzer_size_kW
        outputs["OpEx"] = self.config.fixed_om_USD_per_kW_per_year * electrolyzer_size_kW
