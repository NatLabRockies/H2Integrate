import numpy as np

from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


class DemandFollowingControl(SystemLevelControlBase):
    """Demand-following system-level controller.

    Dispatch priority:
    1. Curtailable techs run at rated capacity (zero marginal cost).
    2. Storage absorbs surplus / provides deficit (set_point = net demand).
    3. Remaining demand is split equally across dispatchable techs.

    This strategy always attempts to meet demand exactly; it does not
    consider costs.
    """

    def compute(self, inputs, outputs):
        demand = inputs[self.demand_input_name].copy()

        # 1. Curtailable techs: full production
        demand = self._subtract_curtailable(inputs, outputs, demand)

        # 2. Storage dispatch
        demand = self._dispatch_storage(inputs, outputs, demand)

        # 3. Dispatchable techs: equal share of remaining demand
        remaining = np.maximum(demand, 0.0)
        n_dispatchable = len(
            [
                s
                for s in self.dispatchable_techs
                if self.commodity in self._get_commodity_for_tech(s)
            ]
        )

        # calculate the number of dispatchable technologies that
        # produce the demanded commodity
        if n_dispatchable > 0:
            share = remaining / n_dispatchable
            for set_point_name, commodity in zip(
                self.dispatchable_set_point_names, self.dispatchable_commodity_names
            ):
                if commodity == self.commodity:
                    outputs[set_point_name] = share

        # Check for nans or inf
        if not all(np.isfinite(c).all() for k, c in outputs.items()):
            buggy_outputs = [k for k, c in outputs.items() if not np.isfinite(c).all()]
            raise ValueError(f"Buggy outputs {buggy_outputs}")
        if not all(np.isfinite(c).all() for k, c in inputs.items()):
            buggy_inputs = [k for k, c in inputs.items() if not np.isfinite(c).all()]
            raise ValueError(f"Buggy inputs {buggy_inputs}")
