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
        for curtailable_tech in self.curtailable_techs:
            commodity_from_tech = self._get_commodity_for_tech(curtailable_tech)
            # check that this tech produces the commodity demanded
            if self.commodity in commodity_from_tech:
                # if the commodity produced from a tech is the demanded commodity
                # then subtract the curtailable production from the demand
                demand = self._subtract_curtailable(
                    curtailable_tech, demand, self.commodity, inputs, outputs
                )

        # 2. Storage dispatch
        # number of storage components that produce the demanded commodity
        n_storage = len(
            [s for s in self.storage_techs if self.commodity in self._get_commodity_for_tech(s)]
        )
        for storage_tech in self.storage_techs:
            commodity_from_tech = self._get_commodity_for_tech(storage_tech)
            if self.commodity in commodity_from_tech:
                demand = self._dispatch_storage(
                    storage_tech, demand / n_storage, self.commodity, inputs, outputs
                )

        # 3. Dispatchable techs: equal share of remaining demand
        remaining = np.maximum(demand, 0.0)

        # calculate the number of dispatchable technologies that
        # produce the demanded commodity
        n_dispatchable = len(
            [
                s
                for s in self.dispatchable_techs
                if self.commodity in self._get_commodity_for_tech(s)
            ]
        )
        for dispatchable_tech in self.dispatchable_techs:
            commodity_from_tech = self._get_commodity_for_tech(dispatchable_tech)
            if self.commodity in commodity_from_tech:
                outputs[f"{dispatchable_tech}_{self.commodity}_set_point"] = (
                    remaining / n_dispatchable
                )

        # Check for nans or inf
        if not all(np.isfinite(c).all() for k, c in outputs.items()):
            bad_outputs = [k for k, c in outputs.items() if not np.isfinite(c).all()]
            raise ValueError(f"These outputs contain non-finite values: {bad_outputs}")
        if not all(np.isfinite(c).all() for k, c in inputs.items()):
            bad_inputs = [k for k, c in inputs.items() if not np.isfinite(c).all()]
            raise ValueError(f"These inputs contain non-finite values: {bad_inputs}")
