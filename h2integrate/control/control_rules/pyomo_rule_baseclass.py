import openmdao.api as om
import pyomo.environ as pyo
from attrs import field, define

from h2integrate.core.utilities import BaseConfig


@define(kw_only=True)
class PyomoRuleBaseConfig(BaseConfig):
    """
    Configuration class for the PyomoRuleBaseConfig.

    This class defines the parameters required to configure the `PyomoRuleBaseConfig`.

    Attributes:
        commodity_name (str): Name of the commodity being controlled (e.g., "hydrogen").
        commodity_units (str): Units of the commodity (e.g., "kg/h").
    """

    commodity_name: str = field()
    commodity_storage_units: str = field()


class PyomoRuleBaseClass(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = PyomoRuleBaseConfig.from_dict(
            self.options["tech_config"]["model_inputs"]["dispatch_rule_parameters"]
        )

        self.add_discrete_output(
            "dispatch_block_rule_function",
            val=self.dispatch_block_rule_function,
            desc="pyomo port creation function",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Return the Pyomo model elements for a given technology through the OpenMDAO
        infrastructure.

        No computations are required for PyomoRuleClass children. All the work should be done in
        setup via the dispatch_block_rule_function() method.
        """

        pass

    def dispatch_block_rule_function(self, pyomo_model: pyo.ConcreteModel, tech_name: str):
        """
        Creates and initializes pyomo dispatch model components for a specific technology.

        This method sets up all model elements (parameters, variables, constraints,
        and ports) associated with a technology block within the dispatch model.
        It is typically called in the setup_pyomo() method of the PyomoControllerBaseClass.

        Args:
            pyomo_model (pyo.ConcreteModel): The Pyomo model to which the technology
                components will be added.
            tech_name (str): The name or key identifying the technology (e.g., "battery",
                "electrolyzer") for which model components are created.
        """
        # Parameters
        self._create_parameters(pyomo_model, tech_name)
        # Variables
        self._create_variables(pyomo_model, tech_name)
        # Constraints
        self._create_constraints(pyomo_model, tech_name)
        # Ports
        self._create_ports(pyomo_model, tech_name)

    def _create_parameters(self, pyomo_model, tech_name: str):
        """Defines technology-specific Pyomo parameters for the given model.

        This abstract method should be implemented by subclasses to create and add
        technology-specific Pyomo parameters (e.g., efficiencies, limits, or costs)
        to the provided model instance.

        Args:
            pyomo_model: The Pyomo model instance to which parameters will be added.
            tech_name (str): The name or identifier of the technology for which
                parameters are defined.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")

    def _create_variables(self, pyomo_model, tech_name: str):
        """Defines technology-specific Pyomo variables for the given model.

        This abstract method should be implemented by subclasses to create and add
        technology-specific Pyomo variables (e.g., efficiencies, limits, or costs)
        to the provided model instance.

        Args:
            pyomo_model: The Pyomo model instance to which variables will be added.
            tech_name (str): The name or identifier of the technology for which
                variables are defined.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError(
            "This method should be implemented in a subclass. \
                                  If no variables to add, simply use a pass function"
        )

    def _create_constraints(self, pyomo_model, tech_name: str):
        """Defines technology-specific Pyomo constraints for the given model.

        This abstract method should be implemented by subclasses to create and add
        technology-specific Pyomo constraints (e.g., efficiencies, limits, or costs)
        to the provided model instance.

        Args:
            pyomo_model: The Pyomo model instance to which constraints will be added.
            tech_name (str): The name or identifier of the technology for which
                constraints are defined.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError(
            "This method should be implemented in a subclass. \
                                  If no constraints to add, simply use a pass function"
        )

    def _create_ports(self, pyomo_model, tech_name: str):
        """Defines technology-specific Pyomo ports for the given model.

        This abstract method should be implemented by subclasses to create and add
        technology-specific Pyomo ports (e.g., efficiencies, limits, or costs)
        to the provided model instance.

        Args:
            pyomo_model: The Pyomo model instance to which ports will be added.
            tech_name (str): The name or identifier of the technology for which
                port are defined.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")
