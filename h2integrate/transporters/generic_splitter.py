import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import contains, range_val_or_none


@define(kw_only=True)
class GenericSplitterPerformanceConfig(BaseConfig):
    """Configuration class for the GenericSplitterPerformanceModel.

    Attributes:
        split_mode (str): what method to use to split input commodity stream.
            Must be either "prescribed_commodity" or "fraction" to split commodity stream.
        commodity (str): name of commodity
        commodity_units (str): units of commodity production profile
        fraction_to_priority_tech (float, optional): fraction of input commodity to
            send to first output stream. Only used if `split_mode` is "fraction".
            Defaults to None.
        prescribed_commodity_to_priority_tech (float, optional): constant amount
            of input commodity to send to first output stream in same units as ``commodity_units``.
            Only used if `split_mode` is "prescribed_commodity". Defaults to None.
    """

    split_mode: str = field(
        converter=(str.lower, str.strip), validator=contains(["prescribed_commodity", "fraction"])
    )
    commodity: str = field(converter=(str.lower, str.strip))
    commodity_units: str = field()
    fraction_to_priority_tech: float = field(default=None, validator=range_val_or_none(0, 1))
    prescribed_commodity_to_priority_tech: float = field(default=None)

    def __attrs_post_init__(self):
        """Validate that the required fields are present based on split_mode."""
        if self.split_mode == "fraction":
            if self.fraction_to_priority_tech is None:
                raise ValueError(
                    "fraction_to_priority_tech is required" " when split_mode is 'fraction'"
                )
        if self.split_mode == "prescribed_commodity":
            if self.prescribed_commodity_to_priority_tech is None:
                raise ValueError(
                    "prescribed_commodity_to_priority_tech is required"
                    " when split_mode is 'prescribed_commodity'"
                )

        # Set default values for unused fields
        if self.split_mode == "fraction" and self.prescribed_commodity_to_priority_tech is None:
            self.prescribed_commodity_to_priority_tech = 0.0
        elif self.split_mode == "prescribed_commodity" and self.fraction_to_priority_tech is None:
            self.fraction_to_priority_tech = 0.0


class GenericSplitterPerformanceModel(om.ExplicitComponent):
    """
    Split commodity from one source into two outputs.

    This component supports two splitting modes:
    1. Fraction-based splitting: Split based on a specified fraction sent to the priority technology
    2. Prescribed commodity splitting: Send a prescribed amount to the priority technology,
       remainder to the other technology

    The priority_tech parameter determines which technology receives the primary allocation.
    The outputs are:
    - {commodity}_out1: commodity sent to the first technology
    - {commodity}_out2: commodity sent to the second technology

    This component is purposefully simple; a more realistic case might include
    losses or other considerations from system components.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict, default={})
        self.options.declare("plant_config", types=dict, default={})
        self.options.declare("tech_config", types=dict, default={})

    def setup(self):
        # Initialize config from tech config
        self.config = GenericSplitterPerformanceConfig.from_dict(
            self.options["tech_config"]["model_inputs"]["performance_parameters"]
        )

        self.add_input(
            f"{self.config.commodity}_in",
            val=0.0,
            shape_by_conn=True,
            units=self.config.commodity_units,
        )

        split_mode = self.config.split_mode

        if split_mode == "fraction":
            self.add_input(
                "fraction_to_priority_tech",
                val=self.config.fraction_to_priority_tech,
                desc="Fraction of input commodity to send to the priority technology (0.0 to 1.0)",
            )
        elif split_mode == "prescribed_commodity":
            self.add_input(
                "prescribed_commodity_to_priority_tech",
                val=self.config.prescribed_commodity_to_priority_tech,
                copy_shape=f"{self.config.commodity}_in",
                units=self.config.commodity_units,
                desc="Prescribed amount of commodity to send to the priority technology",
            )

        self.add_output(
            f"{self.config.commodity}_out1",
            val=0.0,
            copy_shape=f"{self.config.commodity}_in",
            units=self.config.commodity_units,
            desc=f"{self.config.commodity} output to the first technology",
        )
        self.add_output(
            f"{self.config.commodity}_out2",
            val=0.0,
            copy_shape=f"{self.config.commodity}_in",
            units=self.config.commodity_units,
            desc=f"{self.config.commodity} output to the second technology",
        )

    def compute(self, inputs, outputs):
        commodity_in = inputs[f"{self.config.commodity}_in"]
        split_mode = self.config.split_mode

        if split_mode == "fraction":
            fraction_to_priority = inputs["fraction_to_priority_tech"]
            # Ensure fraction is between 0 and 1
            fraction_to_priority = np.clip(fraction_to_priority, 0.0, 1.0)
            commodity_to_priority = commodity_in * fraction_to_priority
            commodity_to_other = commodity_in * (1.0 - fraction_to_priority)

        elif split_mode == "prescribed_commodity":
            prescribed_to_priority = inputs["prescribed_commodity_to_priority_tech"]
            # Ensure prescribed commodity is non-negative and doesn't exceed available commodity
            available_commodity = np.maximum(0.0, commodity_in)
            requested_amount = np.maximum(0.0, prescribed_to_priority)
            commodity_to_priority = np.minimum(requested_amount, available_commodity)
            commodity_to_other = commodity_in - commodity_to_priority

        # Determine which output gets priority allocation based on plant config
        # This requires mapping priority_tech to output1 or output2
        # For now, we'll assume priority_tech maps to output1
        # TODO: This mapping logic should be enhanced based on plant configuration
        outputs[f"{self.config.commodity}_out1"] = commodity_to_priority
        outputs[f"{self.config.commodity}_out2"] = commodity_to_other
