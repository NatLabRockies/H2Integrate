import numpy as np

from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


class DemandFollowingControl(SystemLevelControlBase):
    """Demand-following system-level controller.

    Dispatches technologies to meet a time-varying demand profile without
    considering costs. The demand is satisfied in a fixed three-step priority
    order, and each step's shortfall or surplus is passed to the next:

    1. **Curtailable techs** run at their full rated capacity. Their total
       output is subtracted from the demand, which may drive the residual
       demand negative (surplus).

    2. **Storage techs** receive the residual demand (which may be positive
       or negative). When demand is positive the storage is commanded to
       discharge; when negative it is commanded to charge. If multiple
       storage techs produce the demanded commodity, the residual demand is
       split **evenly** across them (each receives ``demand / n_storage``).

    3. **Dispatchable techs** cover any remaining positive demand after
       storage. The remaining demand (floored at zero) is split **evenly**
       across all dispatchable techs that produce the demanded commodity
       (each receives ``remaining_demand / n_dispatchable``).
    """

    def compute(self, inputs, outputs):
        commodity = self.commodity
        demand = inputs[self.demand_input_name].copy()

        # 1. Curtailable techs: operate at full production
        for curtailable_tech in self.curtailable_techs:
            commodity_from_tech = self._get_commodity_for_tech(curtailable_tech)
            # check that this tech produces the commodity demanded
            for tech_commodity in commodity_from_tech:
                if tech_commodity == commodity:
                    # if the commodity produced from a tech is the demanded commodity
                    # then subtract the curtailable production from the demand
                    demand = self._subtract_curtailable(
                        curtailable_tech, demand, commodity, inputs, outputs
                    )
                else:
                    if f"{curtailable_tech}_rated_{tech_commodity}_production" in inputs:
                        # set the set-point as the rated production
                        outputs[f"{curtailable_tech}_{tech_commodity}_set_point"] = inputs[
                            f"{curtailable_tech}_rated_{tech_commodity}_production"
                        ] * np.ones(self.n_timesteps)

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
