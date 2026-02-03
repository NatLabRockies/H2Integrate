import openmdao.api as om
from attrs import field, define
from ard.api import set_up_ard_model

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


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

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        pass


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

    We could almost use the CostModelBaseClass directly, but its setup method
    requires a self.config attribute to be defined, so we create this minimal subclass.
    """

    def setup(self):
        self.config = WindPlantArdModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        pass


class ArdWindPlantModel(om.Group):
    """OpenMDAO Group integrating the Ard wind plant as a sub-problem.

    Subsystems:
        wind_ard_cost (WindArdCostComponent): Necessary for providing cost_year to H2Integrate.
        ard_sub_prob (SubmodelComp): Encapsulated Ard Problem exposing specified inputs/outputs.

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

        # add pass-through cost model to include cost_year as expected by H2Integrate
        self.add_subsystem(
            "wind_ard_cost_compatibility",
            WindArdCostCompatibilityComponent(
                driver_config=self.options["driver_config"],
                plant_config=self.options["plant_config"],
                tech_config=self.options["tech_config"],
            ),
            promotes=["cost_year", "VarOpEx"],
        )

        # add pass-through performance model to include inputs and
        # outputs as expected by H2Integrate
        self.add_subsystem(
            "wind_ard_performance_compatibility",
            WindArdPerformanceCompatibilityComponent(
                driver_config=self.options["driver_config"],
                plant_config=self.options["plant_config"],
                tech_config=self.options["tech_config"],
            ),
            promotes=["cost_year", "VarOpEx"],
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
                ("aepFLORIS.power_farm", "electricity_out"),
                ("tcc.tcc", "CapEx"),
                ("opex.opex", "OpEx"),
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
