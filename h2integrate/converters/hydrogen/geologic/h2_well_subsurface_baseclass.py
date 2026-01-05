import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, CostModelBaseConfig
from h2integrate.core.validators import contains
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.tools.inflation.inflate import inflate_cepci


@define(kw_only=True)
class GeoH2SubsurfacePerformanceConfig(BaseConfig):
    """Configuration for performance parameters in natural and geologic hydrogen subsurface
        well sub-models.

    This class defines key performance parameters shared across both natural and
    stimulated subsurface geologic hydrogen models.

    Attributes:
        borehole_depth (float):
            Total depth of the borehole in meters, potentially including turns.

        well_diameter (str):
            The relative diameter of the well.
            Valid options: `"small"` (e.g., from `OSD3500_FY25.xlsx`) or `"large"`.

        well_geometry (str):
            The geometric structure of the well.
            Valid options: `"vertical"` or `"horizontal"`.

        rock_type (str):
            The type of rock formation being drilled to extract geologic hydrogen.
            Valid options: `"peridotite"` or `"bei_troctolite"`.

        grain_size (float):
            The grain size of the rocks used to extract hydrogen, in meters.
    """

    borehole_depth: float = field()
    well_diameter: str = field(validator=contains(["small", "large"]))
    well_geometry: str = field(validator=contains(["vertical", "horizontal"]))
    rock_type: str = field(validator=contains(["peridotite", "bei_troctolite"]))
    grain_size: float = field()


class GeoH2SubsurfacePerformanceBaseClass(om.ExplicitComponent):
    """OpenMDAO component for modeling the performance of the well subsurface for
        geologic hydrogen.

    This component represents the performance model for geologic hydrogen production,
    which can describe either natural or stimulated hydrogen generation processes.
    All configuration inputs are sourced from a corresponding
    :class:`GeoH2PerformanceConfig` instance.

    Attributes:
        options (dict):
            OpenMDAO options dictionary that must include:
                - `plant_config` (dict): Plant-level configuration parameters.
                - `tech_config` (dict): Technology-specific configuration parameters.
                - `driver_config` (dict): Driver or simulation-level configuration parameters.
        config (GeoH2PerformanceConfig):
            Parsed configuration object containing performance model inputs.

    Inputs:
        borehole_depth (float):
            The total borehole depth, in meters (may include directional sections).

        grain_size (float):
            The characteristic grain size of the rock formation, in meters.

    Outputs:
        wellhead_gas_out (ndarray):
            The wellhead gas production rate profile over a one-year period (8760 hours),
            in kilograms per hour.

        hydrogen_out (ndarray):
            The hydrogen production rate profile over a one-year period (8760 hours),
            in kilograms per hour.

        total_wellhead_gas_produced (float):
            The total wellhead gas produced over the plant lifetime, in kilograms per year.

        total_hydrogen_produced (float):
            The total hydrogen produced over the plant lifetime, in kilograms per year.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        # inputs
        self.add_input("borehole_depth", units="m", val=self.config.borehole_depth)
        self.add_input("grain_size", units="m", val=self.config.grain_size)

        # outputs
        self.add_output("wellhead_gas_out", units="kg/h", shape=(8760,))
        self.add_output("hydrogen_out", units="kg/h", shape=(8760,))
        self.add_output("total_wellhead_gas_produced", val=0.0, units="kg/year")
        self.add_output("total_hydrogen_produced", val=0.0, units="kg/year")


@define(kw_only=True)
class GeoH2SubsurfaceCostConfig(CostModelBaseConfig):
    """Configuration for cost parameters in natural and geologic hydrogen well subsurface
        sub-models.

    This class defines cost parameters that are shared across both natural and
    stimulated (engineered) geologic hydrogen subsurface systems.

    Attributes:
        borehole_depth (float):
            Total depth of the borehole, in meters (may include horizontal turns).

        well_diameter (str):
            Relative diameter of the well.
            Valid options: `"small"` (e.g., `OSD3500_FY25.xlsx`) or `"large"`.

        well_geometry (str):
            Structural configuration of the well.
            Valid options: `"vertical"` or `"horizontal"`.

    """

    borehole_depth: float = field()
    well_diameter: str = field(validator=contains(["small", "large"]))
    well_geometry: str = field(validator=contains(["vertical", "horizontal"]))


class GeoH2SubsurfaceCostBaseClass(CostModelBaseClass):
    """OpenMDAO component for modeling subsurface well costs in a geologic hydrogen plant.

    This component calculates capital and operating costs for subsurface well systems
    in a geologic hydrogen plant, applicable to both natural and stimulated hydrogen
    production modes.

    Attributes:
        config (GeoH2SubsurfaceCostConfig):
            Parsed configuration object containing subsurface cost model parameters.

    Inputs:
        borehole_depth (float):
            Total borehole depth, in meters (may include directional drilling sections).

        wellhead_gas_out (ndarray):
            Wellhead gas production rate profile over the simulation period, in kg/h.

        total_wellhead_gas_produced (float):
            Total wellhead gas produced over the plant lifetime, in kg/year.

    Outputs:
        bare_capital_cost (float):
            Raw capital expenditure (CAPEX) without multipliers, in USD.

        CapEx (float):
            Total effective CAPEX including contracting and contingency multipliers, in USD.

        OpEx (float):
            Total operating expense (OPEX) for the system, in USD/year.

        Fixed_OpEx (float):
            Annual fixed OPEX component that does not scale with hydrogen output, in USD/year.

        Variable_OpEx (float):
            Variable OPEX per kilogram of wellhead gas produced, in USD/kg.
    """

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # inputs
        self.add_input("borehole_depth", units="m", val=self.config.borehole_depth)
        self.add_input(
            "wellhead_gas_out",
            shape=n_timesteps,
            units="kg/h",
            desc=f"Hydrogen production rate in kg/h over {n_timesteps} hours.",
        )
        self.add_input("total_wellhead_gas_produced", val=0.0, units="kg/year")

        # outputs
        self.add_output("bare_capital_cost", units="USD")

    def calc_drill_cost(self, x):
        # Calculates drilling costs from pre-fit polynomial curves
        diameter = self.config.well_diameter
        geometry = self.config.well_geometry
        if geometry == "vertical":
            if diameter == "small":
                coeffs = [0.224997743, 389.2448848, 745141.2795]
            elif diameter == "large":
                coeffs = [0.224897254, 869.2069059, 703617.3915]
        elif geometry == "horizontal":
            if diameter == "small":
                coeffs = [0.247604262, 323.277597, 1058263.661]
            elif diameter == "large":
                coeffs = [0.230514884, 941.8801375, 949091.7254]
        a = coeffs[0]
        b = coeffs[1]
        c = coeffs[2]
        drill_cost = a * x**2 + b * x + c

        year = self.config.cost_year
        drill_cost = inflate_cepci(drill_cost, 2010, year)

        return drill_cost
