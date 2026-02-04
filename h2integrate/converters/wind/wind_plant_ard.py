import openmdao.api as om
from attrs import field, define
from ard.api import set_up_ard_model

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define
class WindPlantArdModelConfig(BaseConfig):
    """Configuration container for Ard wind plant model inputs.

    Attributes:
        ard_system (dict): Dictionary of Ard system / layout parameters (turbine specs,
            layout bounds, wake model settings, etc.) passed through to `set_up_ard_model`.
        ard_data_path (str): Root path to Ard data resources (e.g., turbine libraries).
    """

    ard_system: dict = field()
    ard_data_path: str = field()


class WindArdPerformanceCompatibilityComponent(PerformanceModelBaseClass):
    """The class is needed to allow connecting the Ard cost_year easily in H2Integrate.

    This component takes some of the output of Ard and returns it in the format expected
    by H2Integrate. Some minor calculations are performed to get metrics required by
    H2Integrate.
    """

    def setup(self):
        self.config = WindPlantArdModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"
        super().setup()

        self.hours_per_year = 8760
        self.n_turbines = self.config.ard_system["modeling_options"]["layout"]["N_turbines"]
        turbine_specs = self.config.ard_system["modeling_options"]["windIO_plant"]["wind_farm"][
            "turbine"
        ]
        # windio rated power in W, convert to kW
        self.turbine_rating_kw = turbine_specs["performance"]["rated_power"] * 1e-3
        self.plant_rating_kw = self.n_turbines * self.turbine_rating_kw
        self.plant_capacity = self.plant_rating_kw * self.hours_per_year

        self.add_input(
            "ard_electricity_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
        )

    def compute(self, inputs, outputs):
        ard_electricity_series = inputs["ard_electricity_out"]

        # ard has no concept of time and will simulate for all
        # wind conditions provided, including duplicates. Here we
        # convert for time step length and simulation length
        # to get an estimate of the annual energy production regardless
        # of the length of the simulation
        aep = ard_electricity_series.sum() * (self.fraction_of_year_simulated)

        outputs["electricity_out"] = ard_electricity_series
        outputs["total_electricity_produced"] = ard_electricity_series.sum()
        outputs["annual_electricity_produced"] = aep
        outputs["rated_electricity_production"] = self.plant_rating_kw
        outputs["capacity_factor"] = aep / self.plant_capacity


class WindArdCostCompatibilityComponent(CostModelBaseClass):
    """The class is needed to allow connecting the Ard cost_year easily in H2Integrate.

    We could almost use the CostModelBaseClass directly, but its setup method
    requires a self.config attribute to be defined, so we create this minimal subclass.
    """

    def setup(self):
        self.config = CostModelBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

        self.add_input("ard_CapEx", val=0, units="USD")
        self.add_input("ard_OpEx", val=0.0, units="USD/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        outputs["CapEx"] = inputs["ard_CapEx"]
        outputs["OpEx"] = inputs["ard_OpEx"]


class ArdWindPlantModel(om.Group):
    """OpenMDAO Group integrating the Ard wind plant as a sub-problem.

    Subsystems:
        ard_sub_prob (SubmodelComp): Encapsulated Ard Problem exposing specified inputs/outputs.
        wind_ard_performance_compatibility (WindArdPerformanceCompatibilityComponent):
            Necessary for providing required performance metrics to H2Integrate.
        wind_ard_cost_compatibility (WindArdCostCompatibilityComponent):
            Necessary for providing cost_year to H2Integrate.

    Promoted Inputs:
        spacing_primary: Primary spacing parameter.
        spacing_secondary: Secondary spacing parameter.
        angle_orientation: Orientation angle.
        angle_skew: Skew angle.
        x_substations: X-coordinates of substations.
        y_substations: Y-coordinates of substations.

    Promoted Outputs:
        electricity_out (float): Annual energy production (AEP) in MWh (as provided by ARD/FLORIS).
        CapEx (float): Capital expenditure from ARD turbine & balance of plant cost model.
        OpEx (float): Operating expenditure from ARD.
        boundary_distances (array): Distances from turbines to boundary segments.
        turbine_spacing (array): Inter-turbine spacing metrics.
        cost_year: Cost year from cost component.
        VarOpEx: Variable operating expenditure (currently placeholder).
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = WindPlantArdModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        # create ard model
        ard_input_dict = self.config.ard_system
        ard_data_path = self.config.ard_data_path
        ard_prob = set_up_ard_model(input_dict=ard_input_dict, root_data_path=ard_data_path)

        # add ard to the h2i model as a sub-problem
        subprob_ard = om.SubmodelComp(
            problem=ard_prob,
            inputs=[
                "spacing_primary",
                "spacing_secondary",
                "angle_orientation",
                "angle_skew",
                "x_substations",
                "y_substations",
            ],
            outputs=[
                ("aepFLORIS.power_farm", "ard_electricity_out"),
                ("tcc.tcc", "ard_CapEx"),
                ("opex.opex", "ard_OpEx"),
                "boundary_distances",
                "turbine_spacing",
            ],
        )

        # add the ard sub-problem to the parent group
        self.add_subsystem(
            "ard_sub_prob",
            subprob_ard,
            promotes=["*"],
        )

        # add performance model to include inputs and
        # outputs as expected by H2Integrate
        self.add_subsystem(
            "wind_ard_performance_compatibility",
            WindArdPerformanceCompatibilityComponent(
                driver_config=self.options["driver_config"],
                plant_config=self.options["plant_config"],
                tech_config=self.options["tech_config"],
            ),
            promotes=["*"],
        )

        # add pass-through cost model to include cost_year as expected by H2Integrate
        self.add_subsystem(
            "wind_ard_cost_compatibility",
            WindArdCostCompatibilityComponent(
                driver_config=self.options["driver_config"],
                plant_config=self.options["plant_config"],
                tech_config=self.options["tech_config"],
            ),
            promotes=["*"],
        )
