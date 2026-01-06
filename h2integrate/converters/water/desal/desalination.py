from attrs import field, define

from h2integrate.core.utilities import BaseConfig, CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, must_equal
from h2integrate.converters.water.desal.desalination_baseclass import (
    DesalinationCostBaseClass,
    DesalinationPerformanceBaseClass,
)


@define(kw_only=True)
class ReverseOsmosisPerformanceModelConfig(BaseConfig):
    """Configuration class for the ReverseOsmosisDesalinationPerformanceModel.

    Args:
        freshwater_kg_per_hour (float): Desalination plant capacity represented
            as maximum freshwater requirements of system [kg/hr]
        salinity (str): "seawater" >18,000 ppm or "brackish" <18,000 ppm
        freshwater_density (float): Density of the output freshwater [kg/m**3].
            Default = 997.
    """

    freshwater_kg_per_hour: float = field(validator=gt_zero)
    salinity: str = field(validator=contains(["seawater", "brackish"]))
    freshwater_density: float = field(validator=gt_zero, default=997)


class ReverseOsmosisPerformanceModel(DesalinationPerformanceBaseClass):
    """
    An OpenMDAO component that computes the performance of a reverse osmosis desalination system.
    Takes plantcapacitykgph input and outputs fresh water and electricity required.
    """

    def setup(self):
        super().setup()
        self.config = ReverseOsmosisPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        self.add_output(
            "electricity_in",
            val=0.0,
            units="kW",
            desc="Electricity required to run desalination plant",
        )
        self.add_output("feedwater", val=0.0, units="m**3/h", desc="Feedwater flow rate")

    def compute(self, inputs, outputs):
        freshwater_m3_per_hr = self.config.freshwater_kg_per_hour / self.config.freshwater_density

        if self.config.salinity == "seawater":
            # SWRO: Sea Water Reverse Osmosis, water >18,000 ppm
            # Water recovery
            recovery_ratio = 0.5  # https://www.usbr.gov/research/dwpr/reportpdfs/report072.pdf
            feedwater_m3_per_hr = freshwater_m3_per_hr / recovery_ratio

            # Power required
            energy_conversion_factor = (
                4.0  # [kWh/m^3] SWRO energy_conversion_factor range 2.5 to 4.0 kWh/m^3
            )
            # https://www.sciencedirect.com/science/article/pii/S0011916417321057
            desal_power = freshwater_m3_per_hr * energy_conversion_factor

        if self.config.salinity == "brackish":
            # BWRO: Brackish water Reverse Osmosis, water < 18,000 ppm
            # Water recovery
            recovery_ratio = 0.75  # https://www.usbr.gov/research/dwpr/reportpdfs/report072.pdf
            feedwater_m3_per_hr = freshwater_m3_per_hr / recovery_ratio

            # Power required
            energy_conversion_factor = (
                1.5  # [kWh/m^3] BWRO energy_conversion_factor range 1.0 to 1.5 kWh/m^3
            )
            # https://www.sciencedirect.com/science/article/pii/S0011916417321057

            desal_power = freshwater_m3_per_hr * energy_conversion_factor

            """Note: Mass and Footprint
            Based on Commercial Industrial RO Systems
            https://www.appliedmembranes.com/s-series-seawater-reverse-osmosis-systems-2000-to-100000-gpd.html

            All Mass and Footprint Estimates are estimated from Largest RO System:
            S-308F
            -436 m^3/day
            -6330 kg
            -762 cm (L) x 112 cm (D) x 183 cm (H)

            436 m^3/day = 18.17 m^3/hr = 8.5 m^2, 6330 kg
            1 m^3/hr = .467 m^2, 346.7 kg

            Voltage Codes
            460 or 480v/ 3ph/ 60 Hz
            """
        desal_mass_kg = freshwater_m3_per_hr * 346.7  # [kg]
        desal_size_m2 = freshwater_m3_per_hr * 0.467  # [m^2]

        outputs["water"] = freshwater_m3_per_hr
        outputs["electricity_in"] = desal_power
        outputs["feedwater"] = feedwater_m3_per_hr
        outputs["mass"] = desal_mass_kg
        outputs["footprint"] = desal_size_m2


@define(kw_only=True)
class ReverseOsmosisCostModelConfig(CostModelBaseConfig):
    """Configuration class for the ReverseOsmosisDesalinationCostModel.

    Args:
        freshwater_kg_per_hour (float): Desalination plant capacity represented as
            maximum freshwater requirements of system [kg/hr]
        freshwater_density (float): Density of the output freshwater [kg/m**3].
            Default = 997.
    """

    freshwater_kg_per_hour: float = field(validator=gt_zero)
    freshwater_density: float = field(validator=gt_zero)
    cost_year: int = field(default=2013, converter=int, validator=must_equal(2013))


class ReverseOsmosisCostModel(DesalinationCostBaseClass):
    """
    An OpenMDAO component that computes the cost of a reverse osmosis desalination system.
    """

    def setup(self):
        self.config = ReverseOsmosisCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Cost reference: Table 3 of https://www.nrel.gov/docs/fy16osti/66073.pdf.
        CapEx includes 2.55% financing factor, numbers based on INL report
        https://doi.org/10.2172/1236837 (in Table 10) which came from this report
        https://www-pub.iaea.org/MTCD/Publications/PDF/te_1561_web.pdf
        (Table 6 says 2006 is the currency reference year)
        """
        desal_capex = 32894 * (self.config.freshwater_kg_per_hour / 3600)  # [USD]

        desal_opex = 4841 * (self.config.freshwater_kg_per_hour / 3600)  # [USD/yr]

        outputs["CapEx"] = desal_capex
        outputs["OpEx"] = desal_opex
