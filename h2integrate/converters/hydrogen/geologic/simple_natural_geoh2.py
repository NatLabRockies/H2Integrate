import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.converters.hydrogen.geologic.h2_well_subsurface_baseclass import (
    GeoH2SubsurfacePerformanceConfig,
    GeoH2SubsurfacePerformanceBaseClass,
)


@define(kw_only=True)
class NaturalGeoH2PerformanceConfig(GeoH2SubsurfacePerformanceConfig):
    """Configuration for performance parameters for a natural geologic hydrogen subsurface well.
    This class defines performance parameters specific to **natural** geologic hydrogen
    systems (as opposed to stimulated systems).

    Inherits from:
        GeoH2SubsurfacePerformanceConfig

    Attributes:
        use_prospectivity (bool):
            Whether to use prospectivity parameter (if true), or manually enter H2 conc. (if false)

        site_prospectivity (float):
            Dimensionless site assessment factor representing the natural hydrogen
            production potential of the location.

        wellhead_h2_concentration (float):
            Concentration of hydrogen at the wellhead in mol %.

        initial_wellhead_flow (float):
            Hydrogen flow rate measured immediately after well completion, in kilograms
            per hour (kg/h).

        gas_reservoir_size (float):
            Total amount of hydrogen stored in the geologic accumulation, in tonnes (t).
    """

    use_prospectivity: bool = field()
    site_prospectivity: float = field()
    wellhead_h2_concentration: float = field()
    initial_wellhead_flow: float = field()
    gas_reservoir_size: float = field()


class NaturalGeoH2PerformanceModel(GeoH2SubsurfacePerformanceBaseClass):
    """OpenMDAO component for modeling the performance of a subsurface well for a
        natural geologic hydrogen plant.

    This component estimates hydrogen production performance for **naturally occurring**
    geologic hydrogen systems.

    The modeling approach is informed by the following studies:
        - Mathur et al. (Stanford): https://doi.org/10.31223/X5599G
        - Gelman et al. (USGS): https://doi.org/10.3133/pp1900
        - Tang et al. (Southwest Petroleum University): https://doi.org/10.1016/j.petsci.2024.07.029

    Attributes:
        config (NaturalGeoH2PerformanceConfig):
            Configuration object containing model parameters specific to natural geologic
            hydrogen systems.

    Inputs:
        site_prospectivity (float):
            Dimensionless measure of natural hydrogen production potential at a given site.

        wellhead_h2_concentration (float):
            Concentration of hydrogen at the wellhead in mol %.

        initial_wellhead_flow (float):
            Hydrogen flow rate measured immediately after well completion, in kilograms
            per hour (kg/h).


        gas_reservoir_size (float):
            Total mass of hydrogen stored in the subsurface accumulation, in tonnes (t).

        grain_size (float):
            Rock grain size influencing hydrogen diffusion and reaction rates, in meters
            (inherited from base class).

    Outputs:
        wellhead_h2_concentration_mass (float):
            Mass percentage of hydrogen in the wellhead gas mixture.

        wellhead_h2_concentration_mol (float):
            Molar percentage of hydrogen in the wellhead gas mixture.

        lifetime_wellhead_flow (float):
            Average gas flow rate over the operational lifetime of the well, in kg/h.

        wellhead_gas_out_natural (ndarray):
            Hourly wellhead gas production profile from natural accumulations,
            covering one simulated year (8760 hours), in kg/h.

        max_wellhead_gas (float):
            Maximum wellhead gas output over the system lifetime, in kg/h.
    """

    def setup(self):
        self.config = NaturalGeoH2PerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.add_input("site_prospectivity", units="unitless", val=self.config.site_prospectivity)
        self.add_input(
            "wellhead_h2_concentration", units="percent", val=self.config.wellhead_h2_concentration
        )
        self.add_input("initial_wellhead_flow", units="kg/h", val=self.config.initial_wellhead_flow)
        self.add_input("gas_reservoir_size", units="t", val=self.config.gas_reservoir_size)

        self.add_output("wellhead_h2_concentration_mass", units="percent")
        self.add_output("wellhead_h2_concentration_mol", units="percent")
        self.add_output("lifetime_wellhead_flow", units="kg/h")
        self.add_output("wellhead_gas_out_natural", units="kg/h", shape=(n_timesteps,))
        self.add_output("max_wellhead_gas", units="kg/h")

    def compute(self, inputs, outputs):
        if self.config.rock_type == "peridotite":  # TODO: sub-models for different rock types
            # Calculate expected wellhead h2 concentration from prospectivity
            prospectivity = inputs["site_prospectivity"]
            if self.config.use_prospectivity:
                wh_h2_conc = 58.92981751 * prospectivity**2.460718753  # percent
            else:
                wh_h2_conc = inputs["wellhead_h2_concentration"]

        # Calculated average wellhead gas flow over well lifetime
        init_wh_flow = inputs["initial_wellhead_flow"]
        lifetime = self.options["plant_config"]["plant"]["plant_life"]
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        avg_wh_flow = (-0.193 * np.log(lifetime) + 0.6871) * init_wh_flow  # temp. fit to Arps data

        # Calculated hydrogen flow out
        balance_mw = 23.32  # Note: this is based on Aspen models in aspen_surface_processing.py
        h2_mw = 2.016
        x_h2 = wh_h2_conc / 100
        w_h2 = x_h2 * h2_mw / (x_h2 * h2_mw + (1 - x_h2) * balance_mw)
        avg_h2_flow = w_h2 * avg_wh_flow

        # Parse outputs
        outputs["wellhead_h2_concentration_mass"] = w_h2 * 100
        outputs["wellhead_h2_concentration_mol"] = wh_h2_conc
        outputs["lifetime_wellhead_flow"] = avg_wh_flow
        outputs["wellhead_gas_out_natural"] = np.full(n_timesteps, avg_wh_flow)
        outputs["wellhead_gas_out"] = np.full(n_timesteps, avg_wh_flow)
        outputs["hydrogen_out"] = np.full(n_timesteps, avg_h2_flow)
        outputs["max_wellhead_gas"] = init_wh_flow
        outputs["total_wellhead_gas_produced"] = np.sum(outputs["wellhead_gas_out"])
        outputs["total_hydrogen_produced"] = np.sum(outputs["hydrogen_out"])
