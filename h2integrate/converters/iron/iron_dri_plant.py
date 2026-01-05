from h2integrate.converters.iron.iron_dri_base import (
    IronReductionPlantBaseCostComponent,
    IronReductionPlantBasePerformanceComponent,
)


class HydrogenIronReductionPlantCostComponent(IronReductionPlantBaseCostComponent):
    """Cost component for hydrogen-based direct reduced iron (DRI) plant
    using the Rosner cost model.

    Attributes:
        product (str): 'h2_dri'
        config (HydrogenIronReductionCostConfig): configuration class
        coeff_df (pd.DataFrame): cost coefficient dataframe
        steel_to_iron_ratio (float): steel/pig iron ratio
    """

    def setup(self):
        self.product = "h2_dri"
        super().setup()


class NaturalGasIronReductionPlantCostComponent(IronReductionPlantBaseCostComponent):
    """Cost component for natural gas-based direct reduced iron (DRI) plant
    using the Rosner cost model.

    Attributes:
        product (str): 'ng_dri'
        config (NaturalGasIronReductionCostConfig): configuration class
        coeff_df (pd.DataFrame): cost coefficient dataframe
        steel_to_iron_ratio (float): steel/pig iron ratio
    """

    def setup(self):
        self.product = "ng_dri"
        super().setup()


class HydrogenIronReductionPlantPerformanceComponent(IronReductionPlantBasePerformanceComponent):
    """Performance component for hydrogen-based direct reduced iron (DRI) plant
    using the Rosner performance model.

    Attributes:
        product (str): 'h2_dri'
        config (HydrogenIronReductionPerformanceConfig): configuration class
        coeff_df (pd.DataFrame): performance coefficient dataframe
        steel_to_iron_ratio (float): steel/pig iron ratio
    """

    def setup(self):
        self.product = "h2_dri"
        self.feedstocks_to_units = {
            "natural_gas": "MMBtu",
            "water": "galUS",  # "galUS/h"
            "iron_ore": "t/h",
            "electricity": "kW",
            "hydrogen": "t/h",
        }
        super().setup()


class NaturalGasIronReductionPlantPerformanceComponent(IronReductionPlantBasePerformanceComponent):
    """Performance component for natural gas-based direct reduced iron (DRI) plant
    using the Rosner performance model.

    Attributes:
        product (str): 'ng_dri'
        config (NaturalGasIronReductionPerformanceConfig): configuration class
        coeff_df (pd.DataFrame): performance coefficient dataframe
        steel_to_iron_ratio (float): steel/pig iron ratio
    """

    def setup(self):
        self.feedstocks_to_units = {
            "natural_gas": "MMBtu",
            "water": "galUS",  # "galUS/h"
            "iron_ore": "t/h",
            "electricity": "kW",
            "reformer_catalyst": "(m**3)",  # "(m**3)/h"
        }

        self.product = "ng_dri"
        super().setup()
