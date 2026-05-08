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
        commodity = self.commodity
        demand = inputs[self.demand_input_name].copy()

        # 1. Curtailable techs: operate at full production
        for curtailable_tech in self.curtailable_techs:
            commodity_from_tech = self._get_commodity_for_tech(curtailable_tech)
            # check that this tech produces the commodity demanded
            if commodity in commodity_from_tech:
                # if the commodity produced from a tech is the demanded commodity
                # then subtract the curtailable production from the demand
                demand = self._subtract_curtailable(
                    curtailable_tech, demand, commodity, inputs, outputs
                )

        # 2. Storage dispatch
        # number of storage components that produce the demanded commodity
        n_storage = len(
            [s for s in self.storage_techs if commodity in self._get_commodity_for_tech(s)]
        )
        for storage_tech in self.storage_techs:
            commodity_from_tech = self._get_commodity_for_tech(storage_tech)
            if commodity in commodity_from_tech:
                demand = self._dispatch_storage(
                    storage_tech, demand / n_storage, commodity, inputs, outputs
                )

        # 3. Dispatchable techs
        remaining_demand = np.maximum(demand, 0.0)

        # calculate the number of dispatchable technologies that
        # produce the demanded commodity
        n_dispatchable = len(
            [s for s in self.dispatchable_techs if commodity in self._get_commodity_for_tech(s)]
        )
        for dispatchable_tech in self.dispatchable_techs:
            commodity_from_tech = self._get_commodity_for_tech(dispatchable_tech)
            if commodity in commodity_from_tech:
                outputs[f"{dispatchable_tech}_{commodity}_set_point"] = (
                    remaining_demand / n_dispatchable
                )
