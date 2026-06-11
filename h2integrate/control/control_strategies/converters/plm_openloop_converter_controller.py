import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import contains
from h2integrate.control.control_strategies.storage.openloop_storage_control_base import (
    StorageOpenLoopControlBase,
    StorageOpenLoopControlBaseConfig,
)


@define(kw_only=True)
class PeakLoadManagementHeuristicOpenLoopConverterControllerConfig(
    StorageOpenLoopControlBaseConfig
):
    """
    Configuration class for the PeakLoadManagementHeuristicOpenLoopStorageController.

    Defines peak-selection and dispatch-priority rules used to pre-compute
    an open-loop discharge and recharge schedule.

    Attributes:


    """

    system_capacity_kw: int | float = field()
    demand_profile_peak_cutoff: int | float = field()
    demand_profile_upstream: int | float | list | None = field()
    demand_profile_upstream_peak_cutoff: int | float | None = field()
    demand_profile_upstream_kind: str = field(
        default="electricity", validator=contains(["electricity", "price"])
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()


class PeakLoadManagementHeuristicOpenLoopConverterController(StorageOpenLoopControlBase):
    def setup(self):
        self.config = PeakLoadManagementHeuristicOpenLoopConverterControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            f"system_capacity_{self.config.commodity_rate_units}",
            val=self.config.system_capacity_kw,
            units=f"{self.config.commodity_rate_units}",
            desc="Converter control system awareness of the system capacity",
        )

        # if self.config.demand_profile_upstream_kind == "price":
        #     peak_cutoff_units = f"USD/({self.config.commodity_amount_units})"
        # else:
        #     peak_cutoff_units = self.config.

        self.add_input(
            "demand_profile_upstream_peak_cutoff",
            val=self.config.demand_profile_upstream_peak_cutoff,
            # units=peak_cutoff_units,
            desc="demand_profile_upstream_peak_cutoff",
        )

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.set_point_array = np.zeros(self.n_timesteps)

    def compute(self, inputs, outputs):
        commodity = self.config.commodity
        demand_profile = inputs[f"{commodity}_demand"]
        system_capacity_rate = inputs[f"system_capacity_{self.config.commodity_rate_units}"][0]
        demand_profile_peak_cutoff = self.config.demand_profile_peak_cutoff
        demand_profile_upstream = self.config.demand_profile_upstream
        demand_profile_upstream_peak_cutoff = inputs["demand_profile_upstream_peak_cutoff"]

        for idx, val in enumerate(demand_profile):
            val_upstream = demand_profile_upstream[idx]
            if (
                val > demand_profile_peak_cutoff
                or val_upstream > demand_profile_upstream_peak_cutoff
            ):
                desired_dispatch = val - demand_profile_peak_cutoff

                if self.config.demand_profile_upstream_kind == "electricity":
                    desired_dispatch_upstream = val_upstream - demand_profile_upstream_peak_cutoff
                    self.set_point_array[idx] = min(
                        max(
                            max(desired_dispatch, 0),
                            max(desired_dispatch_upstream, 0),
                        ),
                        val,
                        system_capacity_rate,
                    )
                elif self.config.demand_profile_upstream_kind == "price":
                    if val_upstream > demand_profile_upstream_peak_cutoff:
                        self.set_point_array[idx] = min(
                            max(desired_dispatch, 0),
                            val,
                            system_capacity_rate,
                        )
                else:
                    raise (
                        ValueError(
                            f"Invalid demand_profile_upstream_kind \
                            '{self.config.demand_profile_upstream_kind}'"
                        )
                    )

        outputs[f"{commodity}_set_point"] = self.set_point_array
