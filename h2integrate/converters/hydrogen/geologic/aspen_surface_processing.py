import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.converters.hydrogen.geologic.h2_well_surface_baseclass import (
    GeoH2SurfaceCostConfig,
    GeoH2SurfaceCostBaseClass,
    GeoH2SurfacePerformanceConfig,
    GeoH2SurfacePerformanceBaseClass,
)
from h2integrate.converters.hydrogen.geologic.inputs.curve_fit_processing_utilities import (
    STEAM_CONSTANT,
    load_coeffs,
    refit_coeffs,
    evaluate_performance_curves,
)


@define
class AspenGeoH2SurfacePerformanceConfig(GeoH2SurfacePerformanceConfig):
    """Configuration for performance parameters for a natural geologic hydrogen well surface
    processing system. This class defines performance parameters specific to **natural** geologic
    hydrogen systems (as opposed to stimulated systems).

    Inherits from:
        GeoH2SurfacePerformanceConfig

    Attributes:
        refit_coeffs (bool):
            Whether to re-fit performance curves to ASPEN data. Set to False unless new Aspen data
            has been generated.

        curve_input_fn (str):
            Filename of ASPEN model results file used to generate curve fits. Only used if
            `refit_coeffs` is True. Must be located in the ./inputs directory.

        perf_coeff_fn (str):
            Filename of performance curve coefficients. Will be loaded if `refit_coeffs`
            is False and overwritten if `refit_coeffs` is True. Located in the ./inputs directory.
    """

    refit_coeffs: bool = field()
    curve_input_fn: str = field()
    perf_coeff_fn: str = field()


class AspenGeoH2SurfacePerformanceModel(GeoH2SurfacePerformanceBaseClass):
    """
    ASPEN-based geologic hydrogen surface processing performance model for a
    surface processing system for a natural geologic hydrogen plant.

    This component estimates hydrogen production performance for **naturally occurring**
    geologic hydrogen systems.

    The modeling approach is informed by the following studies:
        - Mathur et al. (Stanford): https://doi.org/10.31223/X5599G

    Attributes:
        config (NaturalGeoH2PerformanceConfig):
            Configuration object containing model parameters specific to natural geologic
            hydrogen systems.

    Inputs:
        perf_coeffs (dict):
            Performance curve coefficients, structured like so:
            {"<output name>": [<list, of, curve, coefficients>]}

    Outputs:
        electricity_consumed (ndarray):
            Hourly electricity consumption profile (8760 hours), in kW.

        water_consumed (ndarray):
            Hourly water consumption profile (8760 hours), in kg/h.

        steam_out (ndarray):
            Hourly steam production profile (8760 hours), in kW thermal.
    """

    def setup(self):
        self.config = AspenGeoH2SurfacePerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.outputs_to_units = {
            "H2 Flow Out": "kg/hr",
            "H2 Conc Out": "% mol",
            "Electricity": "kW",
            "Cooling Water": "kt/h",
            "Steam": "kt/h",
        }
        if self.config.refit_coeffs:
            output_names = [f"{k} [{v}]" for k, v in self.outputs_to_units.items()]

            coeffs = refit_coeffs(
                self.config.curve_input_fn, self.config.perf_coeff_fn, output_names
            )
        else:
            output_names = [
                f"{k} [{v}/(kg/hr H2 in)]" if "%" not in v else f"{k} [{v}]"
                for k, v in self.outputs_to_units.items()
            ]

            coeffs = load_coeffs(self.config.perf_coeff_fn, output_names)

        self.add_input("max_wellhead_gas", val=-1.0, units="kg/h")
        self.add_discrete_input("perf_coeffs", val=coeffs)

        self.add_output("electricity_consumed", val=-1.0, shape=(n_timesteps,), units="kW")
        self.add_output("water_consumed", val=-1.0, shape=(n_timesteps,), units="kt/h")
        self.add_output("steam_out", val=-1.0, shape=(n_timesteps,), units="kt/h")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Compute performance outputs based on wellhead conditions."""
        # Extract inputs
        perf_coeffs = discrete_inputs["perf_coeffs"]
        wellhead_flow_kg_hr = inputs["wellhead_gas_in"]
        wellhead_cap_kg_hr = inputs["max_flow_in"]

        if self.config.size_from_wellhead_flow:
            wellhead_cap_kg_hr = np.max(wellhead_flow_kg_hr)

        wellhead_h2_conc = inputs["wellhead_h2_concentration_mol"] / 100.0
        outputs["max_flow_size"] = wellhead_cap_kg_hr

        # Evaluate all performance curves
        curve_names = [
            f"{k} [{v}/(kg/hr H2 in)]" if "%" not in v else f"{k} [{v}]"
            for k, v in self.outputs_to_units.items()
        ]

        curve_results = evaluate_performance_curves(
            wellhead_h2_conc, wellhead_cap_kg_hr, perf_coeffs, curve_names
        )

        # Calculate outputs (scaled by actual flow where appropriate)
        h2_out_kg_hr = curve_results["H2 Flow Out [kg/hr/(kg/hr H2 in)]"] * wellhead_flow_kg_hr
        h2_out_conc = curve_results["H2 Conc Out [% mol]"]
        elec_in_kw = curve_results["Electricity [kW/(kg/hr H2 in)]"] * wellhead_flow_kg_hr
        water_in_kt_h = curve_results["Cooling Water [kt/h/(kg/hr H2 in)]"] * wellhead_flow_kg_hr
        steam_out_kt_h = STEAM_CONSTANT

        # Assign outputs
        outputs["hydrogen_out"] = h2_out_kg_hr
        outputs["hydrogen_concentration_out"] = h2_out_conc
        outputs["electricity_consumed"] = elec_in_kw
        outputs["water_consumed"] = water_in_kt_h
        outputs["steam_out"] = steam_out_kt_h
        outputs["total_hydrogen_produced"] = np.sum(h2_out_kg_hr)


@define
class AspenGeoH2SurfaceCostConfig(GeoH2SurfaceCostConfig):
    """Configuration for cost parameters for a natural geologic hydrogen well surface
    processing system. This class defines cost parameters specific to **natural** geologic
    hydrogen systems (as opposed to stimulated systems).

    Inherits from:
        GeoH2SurfaceCostConfig

    Attributes:
        refit_coeffs (bool):
            Whether to re-fit cost curves to ASPEN data. Set to False unless new Aspen data
            has been generated.

        curve_input_fn (str):
            Filename of ASPEN model results file used to generate curve fits. Only used if
            `refit_coeffs` is True. Must be located in the ./inputs directory.

        cost_coeff_fn (str):
            Filename of cost curve coefficients. Will be loaded if `refit_coeffs`
            is False and overwritten if `refit_coeffs` is True. Located in the ./inputs directory.

        op_labor_rate (float):
            Cost of operational labor in $/hr

        overhead_rate (float):
            Fraction of operational labor opex seen in overhead opex

        electricity_price (float):
            Price of electricity in USD/kWh

        water_price (float):
            Price of water in USD/kt
    """

    refit_coeffs: bool = field()
    curve_input_fn: str = field()
    cost_coeff_fn: str = field()
    op_labor_rate: float = field()
    overhead_rate: float = field()
    electricity_price: float = field()
    water_price: float = field()


class AspenGeoH2SurfaceCostModel(GeoH2SurfaceCostBaseClass):
    """OpenMDAO component for modeling the cost of a surface processing system for a
        natural geologic hydrogen plant based on curve fits from an ASPEN model.

    This component estimates hydrogen production cost for **naturally occurring**
    geologic hydrogen systems.

    The modeling approach is informed by the following studies:
        - Mathur et al. (Stanford): https://doi.org/10.31223/X5599G

    Attributes:
        config (NaturalGeoH2CostConfig):
            Configuration object containing model parameters specific to natural geologic
            hydrogen systems.

    Inputs:
        cost_coeffs (dict):
            Performance curve coefficients, structured like so:
            {"<output name>": [<list, of, curve, coefficients>]}

        op_labor_rate (float):
            Cost of operational labor in $/hr

        overhead_rate (float):
            Fraction of operational labor opex seen in overhead opex

        electricity_price (float):
            Price of electricity in USD/kWh

        water_price (float):
            Price of water in USD/kt

        electricity_consumed (ndarray):
            Hourly electricity consumption profile (8760 hours), in kW.

        water_consumed (ndarray):
            Hourly water consumption profile (8760 hours), in kg/h.

    Outputs:
        All inherited from GeoH2SurfaceCostBaseClass
    """

    def setup(self):
        self.config = AspenGeoH2SurfaceCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        if self.config.refit_coeffs:
            output_names = ["Capex [USD]", "Labor [op/shift]"]
            coeffs = refit_coeffs(
                self.config.curve_input_fn, self.config.cost_coeff_fn, output_names
            )
        else:
            output_names = [
                "Capex [USD/(kg/hr H2 in)]",
                "Labor [op/shift/(kg/hr H2 in)]",
            ]
            coeffs = load_coeffs(self.config.cost_coeff_fn, output_names)

        self.add_discrete_input("cost_coeffs", val=coeffs)

        self.add_input("op_labor_rate", val=self.config.op_labor_rate, units="USD/h")
        self.add_input("overhead_rate", val=self.config.overhead_rate, units="unitless")
        self.add_input("electricity_price", val=self.config.electricity_price, units="USD/kW/h")
        self.add_input("water_price", val=self.config.water_price, units="USD/kt")
        self.add_input("electricity_consumed", val=-1.0, shape=(n_timesteps,), units="kW")
        self.add_input("water_consumed", val=-1.0, shape=(n_timesteps,), units="kt/h")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Compute cost outputs based on wellhead conditions and operating parameters."""
        if self.config.cost_from_fit:
            # Extract inputs
            cost_coeffs = discrete_inputs["cost_coeffs"]
            wellhead_cap_kg_hr = inputs["max_flow_size"]
            wellhead_h2_conc = inputs["wellhead_hydrogen_concentration"] / 100.0
            op_labor_rate = inputs["op_labor_rate"]
            overhead_rate = inputs["overhead_rate"]
            electricity_price = inputs["electricity_price"]
            water_price = inputs["water_price"]
            electricity_consumed = inputs["electricity_consumed"]
            water_consumed = inputs["water_consumed"]

            # Evaluate cost curves
            curve_names = [
                "Capex [USD/(kg/hr H2 in)]",
                "Labor [op/shift/(kg/hr H2 in)]",
            ]

            curve_results = evaluate_performance_curves(
                wellhead_h2_conc, wellhead_cap_kg_hr, cost_coeffs, curve_names
            )

            # Calculate capital expenditure
            capex_usd = curve_results["Capex [USD/(kg/hr H2 in)]"] * wellhead_cap_kg_hr
            outputs["CapEx"] = capex_usd

            # Calculate fixed operating expenditure (labor + overhead)
            # Note: Currently using fixed labor count of 5. instead of fitted labor_op_shift
            labor_usd_year = 5 * op_labor_rate * 8760
            overhead_usd_year = labor_usd_year * overhead_rate
            outputs["OpEx"] = labor_usd_year + overhead_usd_year

            # Calculate variable operating expenditure (utilities)
            elec_varopex = np.sum(electricity_consumed) * electricity_price
            water_varopex = np.sum(water_consumed) * water_price
            outputs["VarOpEx"] = elec_varopex + water_varopex

        else:
            # Use custom costs if not fitting from curves
            outputs["CapEx"] = inputs["custom_capex"]
            outputs["OpEx"] = inputs["custom_opex"]
