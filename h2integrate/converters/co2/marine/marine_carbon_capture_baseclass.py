import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.model_baseclasses import CostModelBaseClass


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


class MarineCarbonCapturePerformanceBaseClass(om.ExplicitComponent):
    """Base OpenMDAO component for modeling marine carbon capture performance.

    This class provides the basic input/output setup and requires subclassing to
    implement actual CO₂ capture calculations.

    Attributes:
        plant_config (dict): Configuration dictionary for plant-level parameters.
        tech_config (dict): Configuration dictionary for technology-specific parameters.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.add_input(
            "electricity_in", val=0.0, shape=8760, units="W", desc="Hourly input electricity (W)"
        )
        self.add_output(
            "co2_out",
            val=0.0,
            shape=8760,
            units="kg/h",
            desc="Hourly CO₂ capture rate (kg/h)",
        )
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
        self.add_input(
            "co2_capture_mtpy",
            val=0.0,
            units="t/year",
            desc="Annual CO₂ captured (t/year)",
        )
