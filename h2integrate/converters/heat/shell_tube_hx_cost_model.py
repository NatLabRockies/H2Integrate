from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclass import CostModelBaseClass


@define(kw_only=True)
class ShellTubeHXCostModelConfig(BaseConfig):
    """
    Configuration class for the ShellTubeHXCostModel.

    Args:
        cost_year (int): The year for which the cost model is applicable. Default is 2022.
        hx_transfer_area (float): Total heat transfer area of the heat exchanger in square meters.
            Default is 10.0, limited to a range of 10 to 1000 m^2.
        install_factor (float): Installation factor for the heat exchanger. Default is 1.61.
        material_factor (float): Material factor for the heat exchanger. Default is 1.0 for
            carbon steel. Other values can be used for different materials as required
            for higher temperatures.
        opex_percentage (float): Operational expenditure cost as a percentage of the
            capital expenditure. Default is 0.04 (4%).
    """

    cost_year: int = field(default=2022, converter=int, validator=validators.in_([2022]))
    hx_transfer_area: float = field(
        default=10.0,
        converter=float,
        validator=validators.and_(validators.ge(10), validators.lt(1000)),
    )
    install_factor: float = field(default=1.61, converter=float, validator=validators.gt(0))
    material_factor: float = field(default=1.0, converter=float, validator=validators.gt(0))
    opex_percentage: float = field(default=0.04, converter=float, validator=validators.gt(0))


class ShellTubeHXCostModel(CostModelBaseClass):
    """
    This is a cost model for a u-tube shell-and-tube heat exchanger (HX) based on
        Sinnot and Towler (2021).

    - CapEx = (a + b * S^n) * CEPCI_index * install_factor * material_factor
    - OpEx = 4% of CapEx per year
    """

    def setup(self):
        self.config = ShellTubeHXCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "hx_transfer_area",
            val=self.config.hx_transfer_area,
            units="m**2",
            desc="Total heat transfer area of the heat exchanger",
        )
        self.add_input(
            "install_factor",
            val=self.config.install_factor,
            units="unitless",
            desc="Installation factor for the heat exchanger",
        )
        self.add_input(
            "material_factor",
            val=self.config.material_factor,
            units="unitless",
            desc="Material factor for the heat exchanger",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Coefficients for the cost model based on Sinnot and Towler (2021)
        a = 28000
        b = 54
        n = 1.2

        # Cost factors
        year = 816 / 532.9  # CEPCI index of 532.9 for Jan. 2010, scaled to a cost year of 2022
        install = inputs["install_factor"]
        material = inputs["material_factor"]

        # Total heat transfer area of the heat exchanger
        S = inputs["hx_transfer_area"]

        # Total installed costs
        total_installed_costs = (a + b * S**n) * year * install * material

        outputs["CapEx"] = total_installed_costs
        outputs["OpEx"] = self.config.opex_percentage * total_installed_costs
