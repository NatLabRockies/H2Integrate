import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, CostModelBaseConfig
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define
class GeoH2SurfacePerformanceConfig(BaseConfig):
    """Configuration for performance parameters in natural and geologic hydrogen surface
        wellhead processing sub-models.

    This class defines key performance parameters shared across both natural and
    stimulated surface geologic hydrogen models.

    Attributes:
        size_from_wellhead_flow (bool):
            Whether to size the processing system from the wellhead flow (if True) or max_flow_in
        max_flow_in (float):
            The maximum flow of wellhead gas into the system, in kg/hr
    """

    size_from_wellhead_flow: bool = field()
    max_flow_in: float = field()


class GeoH2SurfacePerformanceBaseClass(om.ExplicitComponent):
    """OpenMDAO component for modeling the performance of the wellhead surface processing for
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
        wellhead_gas_in (ndarray):
            The production rate profile of the well over a one-year period (8760 hours),
            in kilograms per hour.
        max_flow_in (float):
            The intake capacity limit of the processing system for wellhead gas in kg/hour.
        wellhead_h2_concentration_mol (float):
            The molar concentration of hydrogen in the wellhead gas (unitless).

    Outputs:
        hydrogen_out (ndarray):
            The production rate profile of surface processing over a one-year period (8760 hours),
            in kilograms per hour of produced gas (H2 with purity of `hydrogen_concentration_out`)
        hydrogen_concentration_out (float):
            The molar concentration of hydrogen in the wellhead gas (unitless).
        total_hydrogen_produced (float):
            The total hydrogen produced over the plant lifetime, in kilograms per year.
        max_flow_size (float):
            The wellhead gas flow in kg/hour used for sizing the system - passed to the cost model.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        # inputs
        self.add_input("wellhead_gas_in", units="kg/h", val=-1.0, shape=(n_timesteps,))
        self.add_input("max_flow_in", units="kg/h", val=self.config.max_flow_in)
        self.add_input("wellhead_h2_concentration_mol", units="mol/mol", val=-1.0)

        # outputs
        self.add_output("hydrogen_out", units="kg/h", shape=(n_timesteps,))
        self.add_output("hydrogen_concentration_out", units="mol/mol", val=-1.0)
        self.add_output("total_hydrogen_produced", val=-1.0, units="kg/year")
        self.add_output("max_flow_size", units="kg/h", val=self.config.max_flow_in)


@define
class GeoH2SurfaceCostConfig(CostModelBaseConfig):
    """Configuration for cost parameters in natural and geologic hydrogen wellhead surface
        sub-models.

    This class defines cost parameters that are shared across both natural and
    stimulated (engineered) geologic hydrogen surface systems.

    Attributes:
        cost_from_fit (bool):
            Whether to cost the processing system from curves (if True) or `capex` and `opex`
        refit_coeffs (bool):
            Whether to re-fit cost curves to ASPEN data
        custom_capex (float):
            A custom capex to use if cost_from_fit is False
        custom_opex (float):
            A custom opex to use if cost_from_fit is False
    """

    cost_from_fit: bool = field()
    refit_coeffs: bool = field()
    custom_capex: float = field()
    custom_opex: float = field()


class GeoH2SurfaceCostBaseClass(CostModelBaseClass):
    """OpenMDAO component for modeling surface processing costs in a geologic hydrogen plant.

    This component calculates capital and operating costs for surface wellhead processing systems
    in a geologic hydrogen plant, applicable to both natural and stimulated hydrogen
    production modes.

    Attributes:
        config (GeoH2SurfaceCostConfig):
            Parsed configuration object containing surface cost model parameters.

    Inputs:
        wellhead_gas_in (ndarray):
            The production rate profile of the well over a one-year period (8760 hours),
            in kilograms per hour.
        max_flow_size (float):
            The wellhead gas flow in kg/hour used for sizing the system.
        wellhead_hydrogen_concentration (float):
            The molar concentration of hydrogen in the wellhead gas (unitless).

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
            Variable OPEX per kilogram of hydrogen produced, in USD/year.
    """

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # inputs
        self.add_input("wellhead_gas_in", units="kg/h", val=-1.0, shape=(n_timesteps,))
        self.add_input("max_flow_size", units="kg/h", val=-1.0)
        self.add_input("wellhead_hydrogen_concentration", units="mol/mol", val=-1.0)
        self.add_input(
            "hydrogen_out",
            shape=n_timesteps,
            units="kg/h",
            desc=f"Hydrogen production rate in kg/h over {n_timesteps} hours.",
        )
        self.add_input("total_hydrogen_produced", val=0.0, units="kg/year")
        self.add_input("custom_capex", val=self.config.custom_capex, units="USD")
        self.add_input("custom_opex", val=self.config.custom_opex, units="USD/year")

        # outputs
        self.add_output("bare_capital_cost", units="USD")
