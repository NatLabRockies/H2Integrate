import openmdao.api as om
from attrs import field, define

from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


class HydrogenTankPerformanceModel(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        config_details = self.options["tech_config"]["details"]
        self.add_input(
            "hydrogen_in",
            val=0.0,
            shape_by_conn=True,
            copy_shape="hydrogen_out",
            units="kg/h",
            desc="Hydrogen input over a year",
        )
        self.add_input(
            "initial_hydrogen", val=0.0, units="kg", desc="Initial amount of hydrogen in the tank"
        )
        self.add_input(
            "total_capacity",
            val=float(config_details["total_capacity"]),
            units="kg",
            desc="Total storage capacity",
        )
        self.add_input(
            "hydrogen_out",
            val=0.0,
            shape_by_conn=True,
            copy_shape="hydrogen_in",
            units="kg/h",
            desc="Hydrogen output over a year",
        )
        self.add_output(
            "stored_hydrogen",
            val=0.0,
            shape_by_conn=True,
            copy_shape="hydrogen_in",
            units="kg",
            desc="Amount of hydrogen stored",
        )

    def compute(self, inputs, outputs):
        initial_hydrogen = inputs["initial_hydrogen"]
        hydrogen_in = inputs["hydrogen_in"]
        hydrogen_out = inputs["hydrogen_out"]

        outputs["stored_hydrogen"] = initial_hydrogen + hydrogen_in - hydrogen_out


@define(kw_only=True)
class TankCostModelConfig(CostModelBaseConfig):
    total_capacity: float = field()


class HydrogenTankCostModel(CostModelBaseClass):
    def setup(self):
        self.config = TankCostModelConfig.from_dict(self.options["tech_config"]["details"])
        super().setup()
        self.add_input(
            "total_capacity",
            val=self.config.total_capacity,
            units="kg",
            desc="Total storage capacity",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        outputs["CapEx"] = inputs["total_capacity"] * 0.1
        outputs["OpEx"] = inputs["total_capacity"] * 0.01
