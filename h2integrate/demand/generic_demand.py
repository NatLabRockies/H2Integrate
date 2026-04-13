from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.demand.demand_base import DemandComponentBase, DemandComponentBaseConfig


class GenericDemandComponent(DemandComponentBase):
    """Component for for converting input supply into met demand.

    This component computes unmet demand, unused (curtailed) production, and
    the resulting commodity output profile based on the incoming supply and an
    externally specified demand profile. It uses simple arithmetic rules:

    * If demand exceeds supplied commodity, the difference is unmet demand.
    * If supply exceeds demand, the excess is unused (curtailed) commodity.
    * Output equals supplied commodity minus curtailed commodity.

    This component relies on configuration provided through the
    ``tech_config`` dictionary, which must define the demand's
    ``performance_parameters``.
    """

    def setup(self):
        self.config = DemandComponentBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
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

                    * ``unmet_{commodity}_demand_out``: Unmet demand.
                    * ``unused_{commodity}_out``: Curtailed production.
                    * ``{commodity}_out``: Actual output delivered.

        Notes:
            All variables operate on a per-timestep basis and typically have
            array shape ``(n_timesteps,)``.
        """

        outputs = self.calculate_outputs(
            inputs[f"{self.commodity}_in"], inputs[f"{self.commodity}_demand"], outputs
        )
