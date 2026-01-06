from attrs import field, define

from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gte_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class ATBWindPlantCostModelConfig(CostModelBaseConfig):
    """Configuration class for the ATBWindCostModel.
    Recommended to use with wind models (Land-Based, Offshore and Distributed
    More information on ATB methodology and representative wind technologies can
    be found `here <https://atb.nrel.gov/electricity/2024/technologies>`_
    Reference cost values can be found on the `Land-Based Wind`,
    `Fixed-Bottom Offshore Wind`, `Floating Offshore Wind` or `Distributed Wind`
    sheet of the `NREL ATB workbook <https://atb.nrel.gov/electricity/2024/data>`_.

    Attributes:
        capex_per_kW (float|int): capital cost of wind system in $/kW
        opex_per_kW_per_year (float|int): annual operating cost of wind
            system in $/kW/year
    """

    capex_per_kW: float | int = field(validator=gte_zero)
    opex_per_kW_per_year: float | int = field(validator=gte_zero)


class ATBWindPlantCostModel(CostModelBaseClass):
    """
    OpenMDAO component for calculating wind plant capital and operating expenditures.

    This component calculates the capital expenditure (CapEx) and annual operating
    expenditure (OpEx) of a wind plant based on its rated capacity and cost model
    parameters defined in an `ATBWindPlantCostModelConfig`.

    Attributes:
        config (ATBWindPlantCostModelConfig):
            Configuration object containing per-kW cost parameters for CapEx and OpEx.

    Inputs:
        total_capacity (float):
            Rated capacity of the wind farm [kW].

    Outputs:
        CapEx (float):
            Total capital expenditure of the wind plant.
        OpEx (float):
            Annual operating expenditure of the wind plant.
    """

    def setup(self):
        self.config = ATBWindPlantCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input("total_capacity", val=0.0, units="kW", desc="Wind farm rated capacity in kW")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capex = self.config.capex_per_kW * inputs["total_capacity"]
        opex = self.config.opex_per_kW_per_year * inputs["total_capacity"]

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
