import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import range_val
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

        gas_flow_density (float):
            Density of the wellhead gas flow, in kilograms per cubic meter (kg/m^3).

        ramp_up_time_months (float):
            Number of months after initial flow from the well before full utilization.

        percent_increase_during_rampup (float):
            Percent increase in wellhead flow during ramp-up period in percent (%).

        gas_reservoir_size (float):
            Total amount of hydrogen stored in the geologic accumulation, in tonnes (t).

        use_arps_decline_curve (bool):
            Whether to use the Arps decline curve model for well production decline.

        decline_fit_params (dict):
            (Optional) Parameters for the Arps decline curve model, including:
                - 'Di' (float): Decline rate.
                - 'b' (float): Loss rate.
                - 'fit_name' (str): Name of the well fit to use. If provided, overrides Di and b.
                    Options are "Eagle_Ford" or "Permian" or "Bakken".
    """

    use_prospectivity: bool = field()
    site_prospectivity: float = field()
    wellhead_h2_concentration: float = field()
    initial_wellhead_flow: float = field()
    gas_flow_density: float = field()
    ramp_up_time_months: float = field()
    percent_increase_during_rampup: float = field(validator=range_val(0, 100))
    gas_reservoir_size: float = field()
    use_arps_decline_curve: bool = field()
    decline_fit_params: dict = field(default=None)


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
        self.add_input("gas_flow_density", units="kg/m**3", val=self.config.gas_flow_density)
        self.add_input("gas_reservoir_size", units="t", val=self.config.gas_reservoir_size)
        self.add_input("ramp_up_time", units="yr/12", val=self.config.ramp_up_time_months)
        self.add_input(
            "percent_increase_during_rampup",
            units="percent",
            val=self.config.percent_increase_during_rampup,
            desc="Percent increase in wellhead flow during ramp-up period in percent (%)",
        )

        self.add_output("wellhead_h2_concentration_mass", units="percent")
        self.add_output("wellhead_h2_concentration_mol", units="percent")
        self.add_output("lifetime_wellhead_flow", units="kg/h")
        self.add_output("wellhead_gas_out_natural", units="kg/h", shape=(n_timesteps,))
        self.add_output("max_wellhead_gas", units="kg/h")

    def compute(self, inputs, outputs):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Coerce scalar inputs to Python scalars (handles 0-d and 1-d arrays)
        ramp_up_time = float(np.asarray(inputs["ramp_up_time"]).item())
        percent_increase = float(np.asarray(inputs["percent_increase_during_rampup"]).item())
        init_wh_flow = float(np.asarray(inputs["initial_wellhead_flow"]).item())

        if self.config.rock_type == "peridotite":  # TODO: sub-models for different rock types
            # Calculate expected wellhead h2 concentration from prospectivity
            prospectivity = inputs["site_prospectivity"]
            if self.config.use_prospectivity:
                wh_h2_conc = 58.92981751 * prospectivity**2.460718753  # percent
            else:
                wh_h2_conc = inputs["wellhead_h2_concentration"]

        # Calculated average wellhead gas flow over well lifetime
        init_wh_flow = inputs["initial_wellhead_flow"]

        # Coerce scalar inputs to Python scalars (handles 0-d and 1-d arrays)
        ramp_up_time = float(np.asarray(inputs["ramp_up_time"]).item())
        percent_increase = float(np.asarray(inputs["percent_increase_during_rampup"]).item())
        init_wh_flow = float(np.asarray(inputs["initial_wellhead_flow"]).item())

        # Apply ramp-up assumed linear increase
        ramp_up_steps = int(ramp_up_time * (n_timesteps / 12))  # hrs
        if ramp_up_steps > 0:
            ramp_up_flow = init_wh_flow * ((100 + percent_increase) / 100)
            ramp_up_profile = np.linspace(init_wh_flow, ramp_up_flow, ramp_up_steps)
        else:
            ramp_up_flow = init_wh_flow
        remaining_steps = (
            n_timesteps * self.options["plant_config"]["plant"]["plant_life"] - ramp_up_steps
        )  # remaining time steps in lifetime

        # Use decline curve modeling if selected
        if self.config.use_arps_decline_curve:
            t = np.arange(remaining_steps)  # hrs
            if self.config.decline_fit_params and "fit_name" in self.config.decline_fit_params:
                # decline curves from literature is in million standard cubic feet per hour
                ramp_up_flow_m3 = ramp_up_flow / inputs["gas_flow_density"]  # m3/h
                # convert from m3/h to million standard cubic feet per hour (MMSCF/h)
                ramp_up_flow_mmscf = ramp_up_flow_m3 / 28316.846592  # 1 MMSCF = 28316.846592 m3

                # fits for MMSCF/h based on flow rates Figure 7 in Tang et al. (2024)
                fit_name = self.config.decline_fit_params["fit_name"]
                if fit_name == "Eagle_Ford":
                    Di = 0.000157
                    b = 0.932
                elif fit_name == "Permian":
                    Di = 0.000087
                    b = 0.708
                elif fit_name == "Bakken":
                    Di = 0.000076
                    b = 0.784
                else:
                    msg = f"Unknown fit_name '{fit_name}' \
                        for Arps decline curve. Valid options are \
                        'Eagle_Ford', 'Permian', or 'Bakken'."
                    raise ValueError(msg)
                decline_profile = self.arps_decline_curve_fit(t, ramp_up_flow_mmscf, Di, b)
                # convert back to kg/h from MMSCF/h
                decline_profile = decline_profile * 28316.846592 * inputs["gas_flow_density"]
            else:
                Di = self.config.decline_fit_params.get("Di")
                b = self.config.decline_fit_params.get("b")
                decline_profile = self.arps_decline_curve_fit(t, ramp_up_flow, Di, b)
        else:
            # linear decline for rest of lifetime
            decline_profile = np.linspace(ramp_up_flow, 0, remaining_steps)

        wh_flow_profile = np.concatenate((ramp_up_profile, decline_profile))

        # Calculated hydrogen flow out
        balance_mw = 23.32  # Note: this is based on Aspen models in aspen_surface_processing.py
        h2_mw = 2.016
        x_h2 = wh_h2_conc / 100
        w_h2 = x_h2 * h2_mw / (x_h2 * h2_mw + (1 - x_h2) * balance_mw)
        avg_h2_flow = w_h2 * wh_flow_profile

        # Parse outputs
        outputs["wellhead_h2_concentration_mass"] = w_h2 * 100
        outputs["wellhead_h2_concentration_mol"] = wh_h2_conc
        outputs["lifetime_wellhead_flow"] = np.average(wh_flow_profile)
        # fill "wellhead_gas_out_natural" with first year profile from wh_flow_profile
        outputs["wellhead_gas_out_natural"] = wh_flow_profile[:n_timesteps]
        outputs["wellhead_gas_out"] = wh_flow_profile[:n_timesteps]
        outputs["hydrogen_out"] = avg_h2_flow[:n_timesteps]
        outputs["max_wellhead_gas"] = ramp_up_flow
        # this is lifetime flow which decreases over time
        outputs["total_wellhead_gas_produced"] = np.average(wh_flow_profile)*n_timesteps
        outputs["total_hydrogen_produced"] = np.sum(outputs["hydrogen_out"])

    def arps_decline_curve_fit(self, t, qi, Di, b):
        """Arps decline curve model based on Arps (1945)
            https://doi.org/10.2118/945228-G.

        Other Relevant literature:
            Tang et al. (2024) https://doi.org/10.1016/j.jngse.2021.103818
            Adapted the Arps model from Table 2 to fit the
            monthly gas rates from Figure 7 to characterize natural hydrogen
            well production decline for the three oil shale wells
            (Bakken, Eagle Ford and Permian).

        Args:
            t (np.array): Well production duration from max production.
            qi (float): Maximum initial production rate.
            Di (float): Decline rate.
            b (float): Loss rate.

        Returns:
            (np.array): Production rate at time t.
        """
        if np.isclose(b, 0):
            return qi * np.exp(-Di * t)
        else:
            return qi / (1 + b * Di * t) ** (1 / b)
