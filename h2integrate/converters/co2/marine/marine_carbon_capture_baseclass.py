from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


@define(kw_only=True)
class MarineCarbonCapturePerformanceConfig(BaseConfig):
    """Configuration options for marine carbon capture performance modeling.

    Attributes:
        number_ed_min (int): Minimum number of ED units to operate.
        number_ed_max (int): Maximum number of ED units available.
        use_storage_tanks (bool): Flag indicating whether to use storage tanks.
        store_hours (float): Number of hours of CO₂ storage capacity (hours).
    """

    number_ed_min: int = field()
    number_ed_max: int = field()
    use_storage_tanks: bool = field()
    store_hours: float = field()


class MarineCarbonCapturePerformanceBaseClass(PerformanceModelBaseClass):
    """Base OpenMDAO component for modeling marine carbon capture performance.

    This class provides the basic input/output setup and requires subclassing to
    implement actual CO₂ capture calculations.

    Attributes:
        plant_config (dict): Configuration dictionary for plant-level parameters.
        tech_config (dict): Configuration dictionary for technology-specific parameters.
    """

    def setup(self):
        self.commodity = "co2"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"
        super().setup()

        self.add_input(
            "electricity_in", val=0.0, shape=8760, units="W", desc="Hourly input electricity (W)"
        )

        # TODO: remove this output once finance models are updated
        self.add_output("co2_capture_mtpy", units="t/year", desc="Annual CO₂ captured (t/year)")


class MarineCarbonCaptureCostBaseClass(CostModelBaseClass):
    """Base OpenMDAO component for modeling marine carbon capture costs.

    This class defines the input/output structure for cost evaluation and should
    be subclassed for implementation.

    Attributes:
        plant_config (dict): Configuration dictionary for plant-level parameters.
        tech_config (dict): Configuration dictionary for technology-specific parameters.
    """

    def setup(self):
        super().setup()
        self.add_input(
            "electricity_in", val=0.0, shape=8760, units="W", desc="Hourly input electricity (W)"
        )
        # TODO: replaced with annual_co2_produced
        self.add_input(
            "co2_capture_mtpy",
            val=0.0,
            units="t/year",
            desc="Annual CO₂ captured (t/year)",
        )
