from h2integrate.converters.steel.steel_eaf_base import (
    ElectricArcFurnacePlantBaseCostComponent,
    ElectricArcFurnacePlantBasePerformanceComponent,
)


class HydrogenEAFPlantCostComponent(ElectricArcFurnacePlantBaseCostComponent):
    """Cost component for hydrogen-based electric arc furnace (EAF) plant
    using the Rosner cost model.

    Attributes:
        product (str): 'h2_eaf'
        config (ElectricArcFurnaceCostBaseConfig): configuration class
        coeff_df (pd.DataFrame): cost coefficient dataframe
    """

    def setup(self):
        self.product = "h2_eaf"
        super().setup()


class NaturalGasEAFPlantCostComponent(ElectricArcFurnacePlantBaseCostComponent):
    """Cost component for natural gas-based electric arc furnace (EAF) plant
    using the Rosner cost model.

    Attributes:
        product (str): 'ng_eaf'
        config (ElectricArcFurnaceCostBaseConfig): configuration class
        coeff_df (pd.DataFrame): cost coefficient dataframe
    """

    def setup(self):
        self.product = "ng_eaf"
        super().setup()


class HydrogenEAFPlantPerformanceComponent(ElectricArcFurnacePlantBasePerformanceComponent):
    """Performance component for hydrogen-based electric arc furnace (EAF) plant
    using the Rosner performance model.

    Attributes:
        product (str): 'h2_eaf'
        config (ElectricArcFurnacePerformanceBaseConfig): configuration class
        coeff_df (pd.DataFrame): performance coefficient dataframe
    """

    def setup(self):
        self.product = "h2_eaf"
        self.feedstocks_to_units = {
            "natural_gas": "MMBtu",
            "water": "galUS",  # "galUS/h"
            "carbon": "t/h",
            "lime": "t/h",
            "pig_iron": "t/h",
            "electricity": "kW",
        }
        super().setup()


class NaturalGasEAFPlantPerformanceComponent(ElectricArcFurnacePlantBasePerformanceComponent):
    """Performance component for natural gas-based electric arc furnace (EAF) plant
    using the Rosner performance model.

    Attributes:
        product (str): 'ng_eaf'
        config (ElectricArcFurnacePerformanceBaseConfig): configuration class
        coeff_df (pd.DataFrame): performance coefficient dataframe
    """

    def setup(self):
        self.feedstocks_to_units = {
            "natural_gas": "MMBtu",
            "water": "galUS",  # "galUS/h"
            "pig_iron": "t/h",
            "electricity": "kW",
        }

        self.product = "ng_eaf"
        super().setup()
