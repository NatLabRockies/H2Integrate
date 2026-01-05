import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.converters.hydrogen.geologic.h2_well_subsurface_baseclass import (
    GeoH2SubsurfacePerformanceConfig,
    GeoH2SubsurfacePerformanceBaseClass,
)


# Globals - molecular weights
M_Fe = 55.8  # kg/kmol
M_H2 = 1.00  # kg/kmol


@define(kw_only=True)
class StimulatedGeoH2PerformanceConfig(GeoH2SubsurfacePerformanceConfig):
    """Configuration parameters for stimulated geologic hydrogen well subsurface
        performance models.

    Defines performance-related parameters specific to *stimulated* geologic hydrogen systems.

    Attributes:
        olivine_phase_vol (float): Volume percent of olivine in the formation [%].
        olivine_fe_ii_conc (float): Mass percent of iron (II) in the olivine [%].
        depth_to_formation (float): Depth below the surface of the caprock that does not
            participate in the reaction [m].
        inj_prod_distance (float): Distance between the injection and production wells [m].
        reaction_zone_width (float): Estimated width of the rock volume participating
            in the reaction [m].
        bulk_density (float): Bulk density of the rock [kg/m³].
        water_temp (float): Temperature of the injected water [°C].
    """

    olivine_phase_vol: float = field()  # vol pct
    olivine_fe_ii_conc: float = field()  # wt pct
    depth_to_formation: float = field()  # meters
    inj_prod_distance: float = field()  # meters
    reaction_zone_width: float = field()  # meters
    bulk_density: float = field()  # kg/m^3
    water_temp: float = field()  # deg C


class StimulatedGeoH2PerformanceModel(GeoH2SubsurfacePerformanceBaseClass):
    """OpenMDAO component modeling the performance of a stimulated geologic hydrogen plant.

    This component estimates hydrogen production from artificially stimulated
    geologic formations (e.g., serpentinization-based systems). The model follows
    methods described in:

        - Mathur et al. (Stanford): https://doi.org/10.31223/X5599G
        - Templeton et al. (UC Boulder): https://doi.org/10.3389/fgeoc.2024.1366268

    All model inputs are provided through :class:`StimulatedGeoH2PerformanceConfig`.

    Attributes:
        config (StimulatedGeoH2PerformanceConfig): Configuration object containing model
            parameters for the stimulated system.

    Inputs (in addition to those in :class:`GeoH2SubsurfacePerformanceBaseClass`):
        olivine_phase_vol (float): Volume percent of olivine in the formation [%].
        olivine_fe_ii_conc (float): Mass percent of iron (II) in the olivine [%].
        depth_to_formation (float): Depth below the surface of the caprock that does not
            participate in the reaction [m].
        inj_prod_distance (float): Distance between the injection and production wells [m].
        reaction_zone_width (float): Estimated width of the rock volume participating
            in the reaction [m].
        bulk_density (float): Bulk density of the rock [kg/m³].
        water_temp (float): Temperature of the injected water [°C].

    Outputs (in addition to those in :class:`GeoH2SubsurfacePerformanceBaseClass`):
        hydrogen_out_stim (ndarray): Hourly hydrogen production profile from stimulation
            over one year (8760 hours) [kg/h].
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = StimulatedGeoH2PerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()

        self.add_input("olivine_phase_vol", units="percent", val=self.config.olivine_phase_vol)
        self.add_input("olivine_fe_ii_conc", units="percent", val=self.config.olivine_fe_ii_conc)
        self.add_input("depth_to_formation", units="m", val=self.config.depth_to_formation)
        self.add_input("inj_prod_distance", units="m", val=self.config.inj_prod_distance)
        self.add_input("reaction_zone_width", units="m", val=self.config.reaction_zone_width)
        self.add_input("bulk_density", units="kg/m**3", val=self.config.bulk_density)
        self.add_input("water_temp", units="C", val=self.config.water_temp)

        self.add_output("hydrogen_out_stim", units="kg/h", shape=n_timesteps)

    def compute(self, inputs, outputs):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        lifetime = self.options["plant_config"]["plant"]["plant_life"]

        # Calculate serpentinization penetration rate
        grain_size = inputs["grain_size"]
        lin_coeff = 1.00e-6
        exp_coeff = -0.000209
        orig_size = 0.0000685  # meters
        temp = inputs["water_temp"]
        serp_rate = (
            lin_coeff
            * np.exp(exp_coeff * (temp - 260) ** 2)
            * 10 ** np.log10(orig_size / grain_size)
        )
        pen_rate = grain_size * serp_rate

        # Model rock deposit size
        height = inputs["borehole_depth"] - inputs["depth_to_formation"]
        length = inputs["inj_prod_distance"]
        width = inputs["reaction_zone_width"]
        rock_volume = height * length * width
        v_olivine = inputs["olivine_phase_vol"] / 100
        n_grains = rock_volume / grain_size**3 * v_olivine
        rho = inputs["bulk_density"]
        X_Fe = inputs["olivine_fe_ii_conc"] / 100

        # Model shrinking reactive particle
        years = np.linspace(1, lifetime, lifetime)
        sec_elapsed = years * 3600 * n_timesteps
        core_diameter = np.maximum(
            np.zeros(len(sec_elapsed)), grain_size - 2 * pen_rate * sec_elapsed
        )
        reacted_volume = n_grains * (grain_size**3 - core_diameter**3)
        reacted_mass = reacted_volume * rho * X_Fe
        h2_produced = reacted_mass * M_H2 / M_Fe

        # Parse outputs
        h2_prod_avg = h2_produced[-1] / lifetime / n_timesteps
        outputs["hydrogen_out_stim"] = h2_prod_avg
        outputs["hydrogen_out"] = h2_prod_avg
        # Until surface processing model is developed, wellhead gas = hydrogen
        outputs["wellhead_gas_out"] = h2_prod_avg
        outputs["total_hydrogen_produced"] = np.sum(outputs["hydrogen_out"])
        outputs["total_wellhead_gas_produced"] = np.sum(outputs["wellhead_gas_out"])
