import numpy as np
import openmdao.api as om
import numpy_financial as npf

from h2integrate.core.annualization import extrapolate_annual_values, time_weighted_annual_means


class AdjustedCapexOpexComp(om.ExplicitComponent):
    """
    OpenMDAO component to adjust CapEx and OpEx values for multiple technologies to a target
    dollar year using inflation.

    This component takes in capital expenditures (CapEx), operational expenditures (OpEx),
    and their associated cost years for each technology, and adjusts them to a specified target
    dollar year using a given inflation rate. The adjusted values are output for each technology,
    along with the total adjusted CapEx and OpEx across all technologies.

    Attributes:
        inflation_rate (float): The annual inflation rate used for cost adjustment.
        target_dollar_year (int): The year to which all costs are adjusted.

    Inputs:
        capex_{tech} (float, USD): Capital expenditure for each technology.
        opex_{tech} (float, USD/year): Operational expenditure for each technology.
        cost_year_{tech} (int): Dollar year for the costs of each technology.

    Outputs:
        capex_adjusted_{tech} (float, USD): CapEx for each technology adjusted to the
            target dollar year.
        opex_adjusted_{tech} (float, USD/year): OpEx for each technology adjusted to the
            target dollar year.
        total_capex_adjusted (float, USD): Total adjusted CapEx across all technologies.
        total_opex_adjusted (float, USD/year): Total adjusted OpEx across all technologies.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("tech_configs", types=dict)
        self.options.declare("plant_config", types=dict)

    def setup(self):
        tech_configs = self.options["tech_configs"]
        plant_config = self.options["plant_config"]
        self.inflation_rate = plant_config["finance_parameters"]["cost_adjustment_parameters"][
            "cost_year_adjustment_inflation"
        ]
        self.target_dollar_year = plant_config["finance_parameters"]["cost_adjustment_parameters"][
            "target_dollar_year"
        ]
        plant_life = self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        for tech in tech_configs:
            self.add_input(f"capex_{tech}", val=0.0, units="USD")
            self.add_input(f"opex_{tech}", val=0.0, units="USD/year")
            self.add_input(f"varopex_{tech}", val=0.0, shape=plant_life, units="USD/year")

            self.add_discrete_input(f"cost_year_{tech}", val=0, desc="Dollar year for costs")

            self.add_output(f"capex_adjusted_{tech}", val=0.0, units="USD")
            self.add_output(f"opex_adjusted_{tech}", val=0.0, units="USD/year")
            self.add_output(f"varopex_adjusted_{tech}", val=0.0, shape=plant_life, units="USD/year")

        self.add_output("total_capex_adjusted", val=0.0, units="USD")
        self.add_output("total_opex_adjusted", val=0.0, units="USD/year")
        self.add_output("total_varopex_adjusted", val=0.0, shape=plant_life, units="USD/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        total_capex_adjusted = 0.0
        total_opex_adjusted = 0.0
        total_varopex_adjusted = np.zeros(self.plant_life)
        for tech in self.options["tech_configs"]:
            capex = inputs[f"capex_{tech}"][0]
            opex = inputs[f"opex_{tech}"][0]
            varopex = inputs[f"varopex_{tech}"]
            cost_year = int(discrete_inputs[f"cost_year_{tech}"])
            periods = self.target_dollar_year - cost_year
            adjusted_capex = -npf.fv(self.inflation_rate, periods, 0.0, capex)
            adjusted_opex = -npf.fv(self.inflation_rate, periods, 0.0, opex)
            adjusted_varopex = -npf.fv(self.inflation_rate, periods, 0.0, varopex)
            outputs[f"capex_adjusted_{tech}"] = adjusted_capex
            outputs[f"opex_adjusted_{tech}"] = adjusted_opex
            outputs[f"varopex_adjusted_{tech}"] = adjusted_varopex
            total_capex_adjusted += adjusted_capex
            total_opex_adjusted += adjusted_opex
            total_varopex_adjusted += adjusted_varopex

        outputs["total_capex_adjusted"] = total_capex_adjusted
        outputs["total_opex_adjusted"] = total_opex_adjusted
        outputs["total_varopex_adjusted"] = total_varopex_adjusted


class AdjustedCapacityFactorComp(om.ExplicitComponent):
    """OpenMDAO component to compute an adjusted capacity factor for a given commodity.

    This component takes a timeseries of commodity production values and splits it into
    365-day plant-year segments (the last may be partial). The rated production is the largest
    segment mean, and each simulated year's capacity factor is its mean production divided by
    the rated production. Capacity factors for plant years beyond the simulated horizon follow
    ``annual_extrapolation_method``, which is only required when more than one simulated year
    segment must be extended.

    Options:
        annual_extrapolation_method (str | None): ``"tile"``, ``"final_sim_value"``, or
            ``"time_averaged_sim_value"``. Defaults to the plant-level
            ``plant.simulation.annual_extrapolation_method``. An override should generally match
            the simulation setting: the finance model divides variable costs by production, so
            mixing methods between capacity factor and variable costs distorts unit costs.

    Inputs:
        {commodity}_produced (array): Timeseries of commodity production values
            with shape ``(n_timesteps,)``. Units are determined by connection.

    Outputs:
        rated_{commodity}_production (float): Largest annual mean commodity production
            across the simulated year segments. Units are copied from the input.
        capacity_factor (array): Capacity factor for each year of plant life,
            with shape ``(plant_life,)``. Unitless.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("commodity_type", types=str)
        self.options.declare("annual_extrapolation_method", default=None, allow_none=True)

    def setup(self):
        self.commodity = self.options["commodity_type"]
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        # Integer dt matches the base classes and plant validation, so the horizon agrees.
        self.dt = int(self.options["plant_config"]["plant"]["simulation"]["dt"])
        self.annual_extrapolation_method = self.options["annual_extrapolation_method"]
        if self.annual_extrapolation_method is None:
            self.annual_extrapolation_method = self.options["plant_config"]["plant"][
                "simulation"
            ].get("annual_extrapolation_method")

        self.add_input(
            f"{self.commodity}_produced",
            val=0.0,
            units_by_conn=True,
            shape=n_timesteps,
        )

        self.add_output(
            f"rated_{self.commodity}_production",
            val=0.0,
            copy_units=f"{self.commodity}_produced",
            shape=1,
        )

        self.add_output(
            "capacity_factor",
            val=1.0,
            units="unitless",
            shape=plant_life,
        )

    def compute(self, inputs, outputs):
        production_timeseries = inputs[f"{self.commodity}_produced"]
        annual_mean_production, annual_durations = time_weighted_annual_means(
            production_timeseries, self.dt
        )
        rated_production = float(np.max(annual_mean_production))
        outputs[f"rated_{self.commodity}_production"] = rated_production

        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        if rated_production == 0.0:
            annual_capacity_factors = np.ones(annual_mean_production.size)
        else:
            annual_capacity_factors = annual_mean_production / rated_production

        outputs["capacity_factor"] = extrapolate_annual_values(
            annual_capacity_factors,
            plant_life,
            self.annual_extrapolation_method,
            simulated_durations_years=annual_durations,
        )
