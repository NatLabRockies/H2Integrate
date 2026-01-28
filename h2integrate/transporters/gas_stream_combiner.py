"""
Gas stream combiner for multivariable streams.

Combines multiple gas streams using mass-weighted averaging for intensive properties
(temperature, pressure, composition) while summing extensive properties (mass flow).
"""

import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.commodity_stream_definitions import multivariable_streams


@define(kw_only=True)
class GasStreamCombinerConfig(BaseConfig):
    """Configuration for the gas stream combiner.

    Attributes:
        stream_type: Type of multivariable stream (e.g., 'wellhead_gas')
        in_streams: Number of inflow streams to combine
    """

    stream_type: str = field(default="wellhead_gas")
    in_streams: int = field(default=2)

    def __attrs_post_init__(self):
        if self.stream_type not in multivariable_streams:
            raise ValueError(
                f"Unknown stream type '{self.stream_type}'. "
                f"Available: {list(multivariable_streams.keys())}"
            )


class GasStreamCombinerPerformanceModel(om.ExplicitComponent):
    """
    Combine multiple gas streams into one using mass-weighted averaging.

    Total mass flow is summed. Temperature, pressure, and compositions are
    mass-weighted averages of the input streams.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = GasStreamCombinerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        stream_def = multivariable_streams[self.config.stream_type]

        # Add inputs for each stream
        for i in range(1, self.config.in_streams + 1):
            for var_name, var_props in stream_def.items():
                self.add_input(
                    f"{var_name}_in{i}",
                    val=0.0,
                    shape=n_timesteps,
                    units=var_props.get("units"),
                    desc=f"Stream {i}: {var_props.get('desc', '')}",
                )

        # Add outputs
        for var_name, var_props in stream_def.items():
            self.add_output(
                f"{var_name}_out",
                val=0.0,
                shape=n_timesteps,
                units=var_props.get("units"),
                desc=f"Combined: {var_props.get('desc', '')}",
            )

        # Identify the flow variable for weighting
        self._flow_var = next((v for v in stream_def.keys() if "flow" in v.lower()), None)
        if self._flow_var is None:
            raise ValueError(f"No flow variable found in '{self.config.stream_type}'")

    def compute(self, inputs, outputs):
        n_streams = self.config.in_streams
        stream_def = multivariable_streams[self.config.stream_type]
        flow_var = self._flow_var

        # Collect mass flows
        mass_flows = [inputs[f"{flow_var}_in{i}"] for i in range(1, n_streams + 1)]
        total_mass_flow = sum(mass_flows)
        outputs[f"{flow_var}_out"] = total_mass_flow

        # Mass-weighted average for other variables
        for var_name in stream_def.keys():
            if var_name == flow_var:
                continue

            weighted_sum = sum(
                inputs[f"{var_name}_in{i}"] * mass_flows[i - 1] for i in range(1, n_streams + 1)
            )

            with np.errstate(divide="ignore", invalid="ignore"):
                outputs[f"{var_name}_out"] = np.where(
                    total_mass_flow > 0, weighted_sum / total_mass_flow, 0.0
                )
