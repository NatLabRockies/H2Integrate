"""
Stub dispatch rule classes for system-level control.

Each class represents a different technology role in the system-level dispatch
optimization. These extend ``PyomoRuleBaseClass`` and will be fully implemented
in a future PR to build the per-tech Pyomo blocks (parameters, variables,
constraints, ports) used by the ``SystemLevelController``.

Roles:
    - **FixedProducerDispatchRule**: Non-controllable producer (e.g., wind, solar).
      Output is a fixed time series; the optimizer can only curtail it.
    - **CurtailableProducerDispatchRule**: Producer whose output can be reduced
      below its available maximum (e.g., wind with curtailment allowed).
    - **DispatchableProducerDispatchRule**: Fully controllable producer (e.g., grid).
      Output can be set anywhere between 0 and its capacity.
    - **FlexibleConsumerDispatchRule**: Consumer whose load can be modulated
      (e.g., electrolyzer that can ramp down).
    - **DemandDispatchRule**: Fixed demand that must be met. Creates an unmet-demand
      slack variable with a penalty cost in the objective.
"""

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.control.control_rules.pyomo_rule_baseclass import (
    PyomoRuleBaseClass,
    PyomoRuleBaseConfig,
)


class FixedProducerDispatchRule(PyomoRuleBaseClass):
    """Dispatch rule for a fixed (non-controllable) producer.

    The producer's output is taken as-is from its time series data.
    No decision variables are created — only a parameter for the available
    production and a port to connect to the system balance constraint.
    """

    def setup(self):
        self.config = PyomoRuleBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "dispatch_rule")
        )
        super().setup()

    def _create_parameters(self, pyomo_model, tech_name):
        pass  # TODO: add available_production Param

    def _create_variables(self, pyomo_model, tech_name):
        pass  # TODO: add production Var (fixed to available)

    def _create_constraints(self, pyomo_model, tech_name):
        pass  # TODO: constrain production == available_production

    def _create_ports(self, pyomo_model, tech_name):
        pass  # TODO: create commodity output port


class CurtailableProducerDispatchRule(PyomoRuleBaseClass):
    """Dispatch rule for a curtailable producer.

    Like FixedProducerDispatchRule, but the optimizer is allowed to
    reduce the output below the available maximum (curtailment).
    """

    def setup(self):
        self.config = PyomoRuleBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "dispatch_rule")
        )
        super().setup()

    def _create_parameters(self, pyomo_model, tech_name):
        pass  # TODO: add available_production Param

    def _create_variables(self, pyomo_model, tech_name):
        pass  # TODO: add production Var with upper bound = available

    def _create_constraints(self, pyomo_model, tech_name):
        pass  # TODO: 0 <= production <= available_production

    def _create_ports(self, pyomo_model, tech_name):
        pass  # TODO: create commodity output port


class DispatchableProducerDispatchRule(PyomoRuleBaseClass):
    """Dispatch rule for a dispatchable (fully controllable) producer.

    The optimizer can set production anywhere between 0 and capacity.
    A marginal cost parameter is included for the objective function.
    """

    def setup(self):
        self.config = PyomoRuleBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "dispatch_rule")
        )
        super().setup()

    def _create_parameters(self, pyomo_model, tech_name):
        pass  # TODO: add capacity Param, marginal_cost Param

    def _create_variables(self, pyomo_model, tech_name):
        pass  # TODO: add production Var bounded [0, capacity]

    def _create_constraints(self, pyomo_model, tech_name):
        pass

    def _create_ports(self, pyomo_model, tech_name):
        pass  # TODO: create commodity output port


class FlexibleConsumerDispatchRule(PyomoRuleBaseClass):
    """Dispatch rule for a flexible consumer.

    The optimizer can modulate consumption between 0 and max capacity.
    """

    def setup(self):
        self.config = PyomoRuleBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "dispatch_rule")
        )
        super().setup()

    def _create_parameters(self, pyomo_model, tech_name):
        pass  # TODO: add max_consumption Param

    def _create_variables(self, pyomo_model, tech_name):
        pass  # TODO: add consumption Var bounded [0, max_consumption]

    def _create_constraints(self, pyomo_model, tech_name):
        pass

    def _create_ports(self, pyomo_model, tech_name):
        pass  # TODO: create commodity input port


class DemandDispatchRule(PyomoRuleBaseClass):
    """Dispatch rule for a fixed demand.

    Creates an unmet-demand slack variable with a high penalty cost in the
    objective function to ensure demand is met when possible.
    """

    def setup(self):
        self.config = PyomoRuleBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "dispatch_rule")
        )
        super().setup()

    def _create_parameters(self, pyomo_model, tech_name):
        pass  # TODO: add demand_profile Param, unmet_demand_penalty Param

    def _create_variables(self, pyomo_model, tech_name):
        pass  # TODO: add unmet_demand Var (non-negative)

    def _create_constraints(self, pyomo_model, tech_name):
        pass  # TODO: supply + unmet_demand >= demand

    def _create_ports(self, pyomo_model, tech_name):
        pass  # TODO: create commodity input port
