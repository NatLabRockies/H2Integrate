import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.control.control_strategies.controller_baseclass import ControllerBaseClass


@define(kw_only=True)
class PassThroughOpenLoopControllerConfig(BaseConfig):
    commodity_name: str = field()
    commodity_units: str = field()


class PassThroughOpenLoopController(ControllerBaseClass):
    """
    A simple pass-through controller for open-loop systems.

    This controller directly passes the input commodity flow to the output without any
    modifications. It is useful for testing, as a placeholder for more complex controllers,
    and for maintaining consistency between controlled and uncontrolled frameworks as this
    'controller' does not alter the system output in any way.
    """

    def setup(self):
        self.config = PassThroughOpenLoopControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control")
        )

        self.add_input(
            f"{self.config.commodity_name}_in",
            shape_by_conn=True,
            units=self.config.commodity_units,
            desc=f"{self.config.commodity_name} input timeseries from production to storage",
        )

        self.add_output(
            f"{self.config.commodity_name}_out",
            copy_shape=f"{self.config.commodity_name}_in",
            units=self.config.commodity_units,
            desc=f"{self.config.commodity_name} output timeseries from plant after storage",
        )

    def compute(self, inputs, outputs):
        """
        Pass through input to output flows.

        Args:
            inputs (dict): Dictionary of input values.
                - {commodity_name}_in: Input commodity flow.
            outputs (dict): Dictionary of output values.
                - {commodity_name}_out: Output commodity flow, equal to the input flow.
        """

        # Assign the input to the output
        outputs[f"{self.config.commodity_name}_out"] = inputs[f"{self.config.commodity_name}_in"]

    def setup_partials(self):
        """
        Declare partial derivatives as unity throughout the design space.

        This method specifies that the derivative of the output with respect to the input is
        always 1.0, consistent with the pass-through behavior.

        Note:
        This method is not currently used and isn't strictly needed if you're creating other
        controllers; it is included as a nod towards potential future development enabling
        more derivative information passing.
        """

        # Get the size of the input/output array
        size = self._get_var_meta(f"{self.config.commodity_name}_in", "size")

        # Declare partials sparsely for all elements as an identity matrix
        # (diagonal elements are 1.0, others are 0.0)
        self.declare_partials(
            of=f"{self.config.commodity_name}_out",
            wrt=f"{self.config.commodity_name}_in",
            rows=np.arange(size),
            cols=np.arange(size),
            val=np.ones(size),  # Diagonal elements are 1.0
        )
