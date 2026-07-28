import warnings

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


@define(kw_only=True)
class DemandFollowingControlConfig(BaseConfig):
    use_average_conversion_factor: bool = field(default=False)


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
    """

    def setup(self):
        super().setup()

        self.config = DemandFollowingControlConfig.from_dict(
            self.options["plant_config"]["system_level_control"].get("control_parameters", {})
        )

    def get_setpoints_for_commodity_subset(
        self, inputs, outputs, commodity, commodity_demand, tech_subset: list | set | None = None
    ):
        # TODO: rename this method
        if tech_subset is None:
            tech_subset = set(self.input_techs)

        fixed_tech_subset = set(self.fixed_techs) & set(tech_subset)
        flexible_tech_subest = set(self.flexible_techs) & set(tech_subset)
        storage_tech_subset = set(self.storage_techs) & set(tech_subset)
        dispatchable_tech_subset = set(self.dispatchable_techs) & set(tech_subset)

        # 1. Fixed techs: always produce, subtract from demand
        for fixed_tech in fixed_tech_subset:
            commodity_from_tech = self._get_commodity_for_tech(fixed_tech)
            for tech_commodity in commodity_from_tech:
                if tech_commodity == commodity:
                    commodity_demand = self._subtract_fixed(
                        fixed_tech, commodity_demand, commodity, inputs
                    )
                    self.tech_demands_set.append((fixed_tech, tech_commodity))

        # 2. Flexible techs: operate at full production
        for flexible_tech in flexible_tech_subest:
            commodity_from_tech = self._get_commodity_for_tech(flexible_tech)
            for tech_commodity in commodity_from_tech:
                if tech_commodity == commodity:
                    commodity_demand = self._subtract_flexible(
                        flexible_tech, commodity_demand, commodity, inputs, outputs
                    )
                    self.tech_demands_set.append((flexible_tech, tech_commodity))
                else:
                    if f"{flexible_tech}_rated_{tech_commodity}_production" in inputs:
                        # set the per-tech set-point as the rated production
                        outputs[f"{flexible_tech}_{tech_commodity}_set_point"] = inputs[
                            f"{flexible_tech}_rated_{tech_commodity}_production"
                        ] * np.ones(self.n_timesteps)
                        self.tech_demands_set.append((flexible_tech, tech_commodity))

        # 3. Storage dispatch
        # number of storage components that produce the demanded commodity
        n_storage = len(
            [s for s in storage_tech_subset if commodity in self._get_commodity_for_tech(s)]
        )
        for storage_tech in storage_tech_subset:
            commodity_from_tech = self._get_commodity_for_tech(storage_tech)
            if commodity in commodity_from_tech:
                commodity_demand = self._dispatch_storage(
                    storage_tech, commodity_demand / n_storage, commodity, inputs, outputs
                )
                self.tech_demands_set.append((storage_tech, commodity))

        # 4. Dispatchable techs
        remaining_demand = np.maximum(commodity_demand, 0.0)

        # calculate the number of dispatchable technologies that
        # produce the demanded commodity
        n_dispatchable = len(
            [s for s in dispatchable_tech_subset if commodity in self._get_commodity_for_tech(s)]
        )
        for dispatchable_tech in dispatchable_tech_subset:
            commodity_from_tech = self._get_commodity_for_tech(dispatchable_tech)
            if commodity in commodity_from_tech:
                outputs[f"{dispatchable_tech}_{commodity}_set_point"] = (
                    remaining_demand / n_dispatchable
                )
                self.tech_demands_set.append((dispatchable_tech, commodity))

        return outputs

    def get_conversion_factors(self, converters, converter_upstreams, inputs):
        conversion_factors = {}
        for converter_info in list(converters):
            input_cmod, tech, output_cmod = converter_info
            tech_ancestors = converter_upstreams[(input_cmod, tech)]
            conversion_ratio = self.get_converter_conversion_ratio(
                inputs, input_cmod, output_cmod, tech, list(tech_ancestors)
            )

            has_nan = np.isnan(conversion_ratio).any()
            has_inf = np.isinf(conversion_ratio).any()
            is_zero = np.all(conversion_ratio == 0.0)
            if has_inf or has_nan or is_zero:
                # not all values are finite
                if is_zero:
                    bad_indices = list(np.arange(0, len(conversion_ratio), 1))
                else:
                    inf_indices = np.argwhere(~np.isfinite(conversion_ratio)).flatten()
                    nan_indices = np.argwhere(~np.isnan(conversion_ratio)).flatten()
                    bad_indices = list(set(inf_indices) | set(nan_indices))

                capacity_ratio = self.get_converter_capacity_conversion_ratio(
                    inputs,
                    input_cmod,
                    output_cmod,
                    tech,
                    list(tech_ancestors),
                )
                conversion_ratio[bad_indices] = capacity_ratio

            if self.config.use_average_conversion_factor:
                conversion_ratio = conversion_ratio.mean()

            conversion_factors[converter_info] = conversion_ratio
        return conversion_factors

    def compute(self, inputs, outputs):
        if not self.multi_commodity_system:
            self.get_setpoints_for_commodity_subset(
                inputs, outputs, self.commodity, inputs[self.demand_input_name].copy()
            )
            return

        converter_conversion_factors = self.get_conversion_factors(
            self.converters, self.converter_upstreams, inputs
        )

        conversion_factor_of_1 = (
            1.0 if self.config.use_average_conversion_factor else np.ones(self.n_timesteps)
        )

        non_converter_conversion_factors = dict(
            zip(
                self.non_converter_conversion_factor_keys,
                [conversion_factor_of_1] * len(self.non_converter_conversion_factor_keys),
            )
        )
        conversion_factors = non_converter_conversion_factors | converter_conversion_factors

        self.tech_demands_set = []

        demand_techs = self.converter_upstreams[(self.commodity, self.demand_tech)]

        outputs = self.get_setpoints_for_commodity_subset(
            inputs,
            outputs,
            self.commodity,
            inputs[self.demand_input_name].copy(),
            tech_subset=demand_techs,
        )

        conversion_factors_tracker = {}
        for recipe_name, recipe in self.conversion_recipes.items():
            commodity_to_demand = recipe_name[1]
            techs_to_demand = self._get_techs_to_demand_from_recipe(recipe_name)
            conversion_factor = self._get_conversion_from_recipe(conversion_factors, recipe)
            demand = inputs[self.demand_input_name].copy() * conversion_factor
            outputs = self.get_setpoints_for_commodity_subset(
                inputs,
                outputs,
                commodity_to_demand,
                demand,
                tech_subset=techs_to_demand,
            )
            conversion_factors_tracker[recipe_name] = conversion_factor
        unset_techs_cmods = self.techs_to_commodities - set(self.tech_demands_set)
        unset_techs = [k for k in list(unset_techs_cmods) if k[0] not in self.feedstock_comps]
        if unset_techs:
            warnings.warn(
                f"Commands not set for these technologies: {unset_techs}", UserWarning, stacklevel=3
            )
