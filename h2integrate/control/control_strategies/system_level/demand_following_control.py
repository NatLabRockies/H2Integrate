import numpy as np
import networkx as nx
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

        # 2. Flexible techs: operate at full production
        for flexible_tech in flexible_tech_subest:
            commodity_from_tech = self._get_commodity_for_tech(flexible_tech)
            for tech_commodity in commodity_from_tech:
                if tech_commodity == commodity:
                    commodity_demand = self._subtract_flexible(
                        flexible_tech, commodity_demand, commodity, inputs, outputs
                    )
                else:
                    if f"{flexible_tech}_rated_{tech_commodity}_production" in inputs:
                        # set the per-tech set-point as the rated production
                        outputs[f"{flexible_tech}_{tech_commodity}_set_point"] = inputs[
                            f"{flexible_tech}_rated_{tech_commodity}_production"
                        ] * np.ones(self.n_timesteps)

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

    def compute(self, inputs, outputs):
        if not self.multi_commodity_system:
            self.get_setpoints_for_commodity_subset(
                inputs, outputs, self.commodity, inputs[self.demand_input_name].copy()
            )
            return

        # should probably also get a list of generators, feedstocks, and storage
        # should also get an idea of what components are in each "step" of the conversion

        converter_order, converter_upstreams = self.find_converter_techs(
            include_feedstock_sources=True
        )

        converter_tech_names = {v[1] for k, v in converter_order.items()}
        converter_cnt = list(converter_order.keys())
        converter_cnt.sort()
        conversion_factors = {}

        demand_converter = None
        demand_commodity = self.demand_input_name.replace("_demand", "")

        # demand_converter = None
        for converter_ii in converter_cnt:
            input_cmod, tech, output_cmod = converter_order[converter_ii]
            tech_ancestors = converter_upstreams[(input_cmod, tech)]
            conversion_ratio = self.get_converter_conversion_ratio(
                inputs,
                input_cmod,
                output_cmod,
                tech,
                list(tech_ancestors),
                return_avg=self.config.use_average_conversion_factor,
            )
            conversion_factors[converter_ii] = conversion_ratio
            # check if the tech has an edge with the demand component
            if output_cmod == demand_commodity:
                demand_converter = str(tech)
            # if self.technology_graph.has_edge(tech,self.demand_tech):
            #     demand_converter = tech
        if demand_converter is None:
            raise ValueError(f"no converters produce the demanded commodity {demand_commodity}")

        if not self.technology_graph.has_edge(demand_converter, self.demand_tech):
            raise ValueError("logic is wrong")
        # node_order = list(self.technology_graph.nodes())
        # nodes_after_last_converter = node_order[node_order.index(tech)+1:]
        inputs[self.demand_input_name].copy()

        list(self.technology_graph.predecessors(self.demand_tech))
        list(nx.all_simple_paths(self.technology_graph, demand_converter, self.demand_tech))

        # if demand_converter is None:
        #     # If a converter isnt directly connected to the demand tech, assume its the last one
        #     # TODO: update so that it finds the converter that IS connected to the demand tech
        #     demand_converter = tech
        # work backward from commodity demand
        converter_cnt.reverse()
        for converter_ii in converter_cnt:
            input_cmod, tech, output_cmod = converter_order[converter_ii]
            # conversion is input_cmod/output_cmod
            tech_ancestors = converter_upstreams[(input_cmod, tech)]
            conversion_factors[converter_ii]
            upstream_techs = converter_upstreams[(input_cmod, tech)]
            upstream_converters = upstream_techs & set(converter_tech_names)
            if len(upstream_converters) == 0:
                # no converters are upstream
                pass
            else:
                # there are converters upstream
                pass

        {k[0] for i, k in converter_order.items() if k[0] != self.commodity}
