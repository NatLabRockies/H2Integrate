import numpy as np

from h2integrate.control.control_strategies.demand_openloop_controller import (
    DemandOpenLoopControlBase,
    DemandOpenLoopControlBaseConfig,
)


class DemandOpenLoopConverterController(DemandOpenLoopControlBase):
    """Open-loop controller for converting input supply into met demand.

    This controller computes unmet demand, unused (curtailed) production, and
    the resulting commodity output profile based on the incoming supply and an
    externally specified demand profile. It uses simple arithmetic rules:

    * If demand exceeds supplied commodity, the difference is unmet demand.
    * If supply exceeds demand, the excess is unused (curtailed) commodity.
    * Output equals supplied commodity minus curtailed commodity.

    This component relies on configuration provided through the
    ``tech_config`` dictionary, which must define the controller's
    ``control_parameters``.
    """

    def setup(self):
        """Set up the load controller configuration.

        Loads the controller configuration from ``tech_config`` and then calls
        the base class ``setup``to create to inputs/outputs.

        Raises:
            KeyError: If the expected configuration keys are missing from
                ``tech_config``.
        """
        self.config = DemandOpenLoopControlBaseConfig.from_dict(
            self.options["tech_config"]["model_inputs"]["control_parameters"]
        )
        super().setup()

    def compute(self, inputs, outputs):
        """Compute unmet demand, unused commodity, and converter output.

        This method compares the demand profile to the supplied commodity for
        each timestep and assigns unmet demand, curtailed production, and
        actual delivered output.

        Args:
            inputs (dict-like): Mapping of input variable names to their
                current values, including:
                    * ``{commodity}_demand``: Demand profile.
                    * ``{commodity}_in``: Supplied commodity.
            outputs (dict-like): Mapping of output variable names where results
                will be written, including:
                    * ``{commodity}_unmet_demand``: Unmet demand.
                    * ``{commodity}_unused_commodity``: Curtailed production.
                    * ``{commodity}_out``: Actual output delivered.

        Notes:
            All variables operate on a per-timestep basis and typically have
            array shape ``(n_timesteps,)``.
        """
        commodity = self.config.commodity_name
        remaining_demand = inputs[f"{commodity}_demand"] - inputs[f"{commodity}_in"]

        # Calculate missed load and curtailed production
        outputs[f"{commodity}_unmet_demand"] = np.where(remaining_demand > 0, remaining_demand, 0)
        outputs[f"{commodity}_unused_commodity"] = np.where(
            remaining_demand < 0, -1 * remaining_demand, 0
        )

        # Calculate actual output based on demand met and curtailment
        outputs[f"{commodity}_out"] = (
            inputs[f"{commodity}_in"] - outputs[f"{commodity}_unused_commodity"]
        )
