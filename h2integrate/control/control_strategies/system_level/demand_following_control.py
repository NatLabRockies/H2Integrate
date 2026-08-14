from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


class DemandFollowingControl(SystemLevelControlBase):
    """Demand-following system-level controller.

    Dispatches technologies to meet a time-varying demand profile without
    considering costs. The demand is satisfied in a fixed four-step priority
    order, and each step's shortfall or surplus is passed to the next:

    1. **Fixed techs** always produce at their rated capacity and cannot be
       controlled. Their total output is subtracted from the demand.

    2. **Flexible techs** run at their available capacity. Their total
       output is subtracted from the demand, which may drive the residual
       demand negative (surplus).

    3. **Storage techs** receive the residual demand (which may be positive
       or negative). When demand is positive the storage is commanded to
       discharge; when negative it is commanded to charge. If multiple
       storage techs produce the demanded commodity, the residual demand is
       split **evenly** across them (each receives ``demand / n_storage``).

    4. **Dispatchable techs** cover any remaining positive demand after
       storage. The remaining demand (floored at zero) is split **evenly**
       across all dispatchable techs that produce the demanded commodity
       (each receives ``remaining_demand / n_dispatchable``).

    For heterogeneous-commodity systems, this four-step order is applied at
    each commodity level: after the demand commodity is dispatched, the demand
    placed on upstream converters (for example a hydrogen electrolyzer feeding
    an ammonia synloop) is translated into demand for their input commodity via
    the configured conversion ratios and the same dispatch is repeated. See
    ``SystemLevelControlBase._run_dispatch``.
    """

    def compute(self, inputs, outputs):
        self._run_dispatch(inputs, outputs)
