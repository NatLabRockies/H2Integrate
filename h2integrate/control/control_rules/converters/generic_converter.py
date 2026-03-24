import pyomo.environ as pyo
from pyomo.network import Port

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.control.control_rules.pyomo_rule_baseclass import (
    PyomoRuleBaseClass,
    PyomoRuleBaseConfig,
)


class PyomoDispatchGenericConverter(PyomoRuleBaseClass):
    def setup(self):
        self.config = PyomoRuleBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "dispatch_rule"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

    def _create_variables(self, pyomo_model: pyo.ConcreteModel, tech_name: str):
        """Create generic converter variables to add to Pyomo model instance.

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model the variables should be added to.
            tech_name (str): The name or key identifying the technology for which
            variables are created.

        """
        rate_units_pyo_str = "/".join(
            f"pyo.units.{u}" for u in self.config.commodity_rate_units.split("/")
        )

        setattr(
            pyomo_model,
            f"{tech_name}_{self.config.commodity}",
            pyo.Var(
                doc=f"{self.config.commodity} generation \
                    from {tech_name} [{self.config.commodity_rate_units}]",
                domain=pyo.NonNegativeReals,
                units=eval(rate_units_pyo_str),
                initialize=0.0,
            ),
        )

    def _create_ports(self, pyomo_model: pyo.ConcreteModel, tech_name: str):
        """Create generic converter port to add to pyomo model instance.

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model the ports should be added to.
            tech_name (str): The name or key identifying the technology for which
            ports are created.

        """
        setattr(
            pyomo_model,
            f"{tech_name}_port",
            Port(
                initialize={
                    f"{tech_name}_{self.config.commodity}": getattr(
                        pyomo_model, f"{tech_name}_{self.config.commodity}"
                    )
                }
            ),
        )

    def _create_parameters(self, pyomo_model: pyo.ConcreteModel, tech_name: str):
        """Create technology Pyomo parameters to add to the Pyomo model instance.

        Method is currently passed but this can serve as a template to add parameters to the Pyomo
        model instance.

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model that parameters are added to.
            tech_name (str): The name or key identifying the technology for which
            parameters are created.

        """

        pass

    def _create_constraints(self, pyomo_model: pyo.ConcreteModel, tech_name: str):
        """Create technology Pyomo parameters to add to the Pyomo model instance.

        Method is currently passed but this can serve as a template to add constraints to the Pyomo
        model instance.

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model that constraints are added to.
            tech_name (str): The name or key identifying the technology for which
            constraints are created.

        """

        pass
