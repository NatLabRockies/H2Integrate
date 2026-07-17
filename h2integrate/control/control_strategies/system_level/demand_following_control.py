import numpy as np
import networkx as nx
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)
import itertools


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
        return outputs

    def get_conversion_factors(self, converter_order, converter_upstreams, inputs):
        conversion_factors = {}
        for converter_ii, converter_info in converter_order.items():
            input_cmod, tech, output_cmod = converter_info
            tech_ancestors = converter_upstreams[(input_cmod, tech)]
            conversion_ratio = self.get_converter_conversion_ratio(
                inputs,
                input_cmod,
                output_cmod,
                tech,
                list(tech_ancestors),
                return_avg=self.config.use_average_conversion_factor,
            )
            if not self.config.use_average_conversion_factor:
                if np.all(np.abs(conversion_ratio) == 0.0):
                    conversion_ratio_val = self.get_converter_capacity_conversion_ratio(
                        inputs,
                        input_cmod,
                        output_cmod,
                        tech,
                        list(tech_ancestors),
                    )
                    conversion_ratio = np.full(
                        len(inputs[self.demand_input_name]), conversion_ratio_val
                    )

            if self.config.use_average_conversion_factor:
                if conversion_ratio == 0.0:
                    conversion_ratio = self.get_converter_capacity_conversion_ratio(
                        inputs,
                        input_cmod,
                        output_cmod,
                        tech,
                        list(tech_ancestors),
                    )
            conversion_factors[converter_ii] = conversion_ratio
            # TODO: update so key is converter_info
        return conversion_factors

    def convert_combined_conversion_factors_to_tech_demand(
        self,
        reversed_grouped_techs,
        simple_graph,
        grouped_techs_compounding_conversion_factors,
        use_simple_keynames=True,
    ):
        tech_groups_demand = {}
        run_with_complex_keynames = False
        for stuff, conv_fac in grouped_techs_compounding_conversion_factors.items():
            output_cmod, input_cmod, tech = stuff
            tech_to_demand = [
                s
                for s in list(simple_graph.predecessors(tech))
                if simple_graph.edges[s, tech].get("commodity", "") == input_cmod
            ]
            if len(tech_to_demand) != 1:
                raise ValueError("Unexpected situation!")
            # f"{input_cmod} demand for {tech_to_demand} so {tech} can make {output_cmod}"
            if tech_to_demand[0] in reversed_grouped_techs:
                {
                    "techs": list(reversed_grouped_techs[tech_to_demand[0]]),
                    "conversion factor": conv_fac,
                }
            else:
                {"techs": tech_to_demand[0], "conversion factor": conv_fac}
            # NOTE: could throw this in a function so that the keys are simple if needed
            # below has complicated keys in case theres a more complex architecture (such as splitters)
            key = (
                (input_cmod, tech_to_demand[0])
                if use_simple_keynames
                else (input_cmod, tech_to_demand[0], (tech, output_cmod))
            )

            if use_simple_keynames and key in tech_groups_demand:
                run_with_complex_keynames = True
                break
        if run_with_complex_keynames:
            result = self.convert_combined_conversion_factors_to_tech_demand(
                self.reversed_grouped_techs,
                simple_graph,
                grouped_techs_compounding_conversion_factors,
                use_simple_keynames=False,
            )
            return result
        return tech_groups_demand

    def compute(self, inputs, outputs):
        if not self.multi_commodity_system:
            self.get_setpoints_for_commodity_subset(
                inputs, outputs, self.commodity, inputs[self.demand_input_name].copy()
            )
            return

        n_timesteps = len(inputs[self.demand_input_name])

        # should probably also get a list of generators, feedstocks, and storage
        # should also get an idea of what components are in each "step" of the conversion

        converter_order, converter_upstreams = self.find_converter_techs(
            include_feedstock_sources=True
        )

        converter_tech_names = {v[1] for k, v in converter_order.items()}
        converter_cnt = list(converter_order.keys())
        converter_cnt.sort()

        # demand_converter = None
        # demand_commodity = self.demand_input_name.replace("_demand", "")

        conversion_factors = self.get_conversion_factors(
            converter_order, converter_upstreams, inputs
        )

        # 1. Get the nodes of the technology graph that aren't a controllable technology
        non_input_techs = (
            set(self.technology_graph.nodes) - set(self.input_techs) - {self.demand_tech}
        )
        # Group together technologies that are connected to a converter
        # I.e., group together an electrolyzer an hydrogen storage,
        # name this group as the shared commodity with a unique number
        grouped_techs = {f"{k[0][0]}-{i}": k[1] for i, k in enumerate(converter_upstreams.items())}
        # 2. Make a dictionary for future-use that has keys of the technology names and the group they belong to
        reversed_grouped_techs = {}
        for k, v in grouped_techs.items():
            for vv in list(v):
                reversed_grouped_techs[vv] = k

        # 3. Add in a conversion factor of 1 for all non-converter technologies
        for tc in self.techs_to_commodities:
            t, c = tc
            if t not in converter_tech_names:
                conversion_factors[(c, t, c)] = (
                    1.0 if self.config.use_average_conversion_factor else np.ones(n_timesteps)
                )

        # 4. Add conversion factors of 1 for the technologies that are non_input_techs
        # Also add these technologies to the reversed_group_techs
        for non_t in list(non_input_techs):
            up_techs = set(self.technology_graph.predecessors(non_t)) - non_input_techs
            down_techs = set(self.technology_graph.successors(non_t)) - non_input_techs

            commod = None
            if up_techs:
                for t in list(up_techs):
                    commod = self.technology_graph.edges[t, non_t].get("commodity", None)
                    if commod is not None:
                        reversed_grouped_techs[non_t] = reversed_grouped_techs[t]
                        break

            if down_techs and commod is None:
                for t in list(down_techs):
                    commod = self.technology_graph.edges[non_t, t].get("commodity", None)
                    if commod is not None:
                        reversed_grouped_techs[non_t] = reversed_grouped_techs[t]
                        break
            conversion_factors[(commod, non_t, commod)] = (
                1.0 if self.config.use_average_conversion_factor else np.ones(n_timesteps)
            )

        # 5. Make the edges of the grouped technologies
        simple_edges_real = []
        for e in list(self.technology_graph.edges(data="commodity")):
            s0, d0, c = e

            s = reversed_grouped_techs.get(s0, s0)
            d = reversed_grouped_techs.get(d0, d0)

            if s != d:
                simple_edges_real.append((s, d, c))
        simple_graph = nx.DiGraph()
        for connection in simple_edges_real:
            # NOTE: this could be done in the above loop
            simple_graph.add_edge(connection[0], connection[1], commodity=connection[2])

        # 6. Get the compounding conversion factors
        in_degs = dict(simple_graph.in_degree)  # number of input things
        # out_degs = dict(simple_graph.out_degree) # number of output things
        starting_techs = {k for k, v in in_degs.items() if v == 0}
        # demand_commodity = self.demand_input_name.split("_demand",-1)[0]
        grouped_techs_compounding_conversion_factors = {}
        for starting_tech in list(starting_techs):
            paths = list(nx.all_simple_paths(simple_graph, starting_tech, self.demand_tech))
            commodity_graph = nx.DiGraph()  # nodes are commodities

            # input_cmod, output_cmod, and tech or group name
            # shouldnt be more than 1 path
            path = paths[0]
            # n_conversions = len(path) - 1 # remove starting tech
            reverse_path = path[::-1]
            # for p0,p1 in zip(path[:-1], path[1:]):

            commodity_conversions = [
                simple_graph.edges[p0, p1].get("commodity", None)
                for p0, p1 in zip(reverse_path[1:], reverse_path[:-1])
            ]
            commodity_nodes = list(itertools.pairwise(commodity_conversions))
            techs = reverse_path[1:]
            for i, commod_node in enumerate(commodity_nodes):
                # ammonia, hydrogen
                down_cmod, up_cmod = commod_node
                commodity_graph.add_edge(down_cmod, up_cmod, tech=techs[i])

            commodity_edges = commodity_graph.edges(data="tech")
            path_conversion = (
                1.0 if self.config.use_average_conversion_factor else np.ones(n_timesteps)
            )

            for edge in commodity_edges:
                # in_cmod is demand of next tech
                out_cmod, in_cmod, tech = edge
                if tech in grouped_techs:
                    techs_in_group = list(grouped_techs[tech])
                    conversion = (
                        1.0 if self.config.use_average_conversion_factor else np.ones(n_timesteps)
                    )
                    for t in techs_in_group:
                        if t in converter_tech_names:
                            conversion *= conversion_factors[(in_cmod, t, out_cmod)]
                        else:
                            conversion *= conversion_factors[(out_cmod, t, out_cmod)]
                    # converter_tech = [t for t in list(grouped_techs[tech]) if t in converter_technologies]
                    # converter_conversion = 1.0
                    # for ct in converter_tech:
                    #     converter_conversion *= conversion_factors[(in_cmod, ct, out_cmod)]
                    # TODO: add check if any other non-converter techs have a non-1 conversion factor
                else:
                    conversion = conversion_factors[(in_cmod, tech, out_cmod)]
                path_conversion *= conversion
                grouped_techs_compounding_conversion_factors[(out_cmod, in_cmod, tech)] = (
                    path_conversion
                )

        # TODO: add logic to get demand converter?
        # demand_converter = None
        # check if the tech has an edge with the demand component
        # if output_cmod == demand_commodity:
        #     demand_converter = str(tech)
        # if self.technology_graph.has_edge(tech,self.demand_tech):
        #     demand_converter = tech
        # if demand_converter is None:
        #     raise ValueError(f"no converters produce the demanded commodity {demand_commodity}")

        # if not self.technology_graph.has_edge(demand_converter, self.demand_tech):
        #     raise ValueError("logic is wrong")
        # # node_order = list(self.technology_graph.nodes())
        # # nodes_after_last_converter = node_order[node_order.index(tech)+1:]

        # # upstream_of_dmd = list(self.technology_graph.predecessors(self.demand_tech))
        # upstream_of_dmd = list(
        #     nx.all_simple_paths(self.technology_graph, demand_converter, self.demand_tech)
        # )
        # upstream_of_dmd_techs = set()
        # for upstream_path in upstream_of_dmd:
        #     techs_upstream = set(upstream_path)
        #     upstream_of_dmd_techs &= techs_upstream

        # # technologies from the last converter to the demand component
        # upstream_of_dmd_techs = upstream_of_dmd_techs - {self.demand_tech}
        # # set the setpoint of all the technologies creating the stream that feeds the demand
        # self.get_setpoints_for_commodity_subset(
        #     inputs,
        #     outputs,
        #     self.commodity,
        #     inputs[self.demand_input_name].copy(),
        #     tech_subset=upstream_of_dmd_techs,
        # )

        # # now go through the rest of the commodity streams and get the demand
        # demand = inputs[self.demand_input_name].copy()
        # converter_cnt.reverse()

        # def compounding_conversion(init_demand, conversion_ratios):
        #     for c in conversion_ratios.items():
        #         init_demand = init_demand * c
        #         yield init_demand

        # for converter_ii in converter_cnt:
        #     input_cmod, tech, output_cmod = converter_order[converter_ii]
        #     conversion_ratio = conversion_factors[converter_ii]
        #     upstream_techs = converter_upstreams[(input_cmod, tech)]
        #     upstream_converters = upstream_techs & set(converter_tech_names)
        #     if len(upstream_converters) == 0:
        #         # no other converters upstream
        #         upstream_commodity_demand = demand * conversion_ratio
        #         # set setpoints
        #         self.get_setpoints_for_commodity_subset(
        #             inputs,
        #             outputs,
        #             output_cmod,  # self.commodity, # should this be output_cmod
        #             upstream_commodity_demand,
        #             tech_subset=upstream_techs,
        #         )

        #     else:
        #         # TODO: finish this bit
        #         # there are converters upstream
        #         # upstream_flows = set()
        #         # for uc in upstream_converters:
        #         #     upstream_tech_flows = {k for k,v in converter_upstreams.items() if k[1] == uc}
        #         #     up_upstream_techs = [converter_upstreams[k] for k in upstream_tech_flows}
        #         #     up_upstream_converters = up_upstream_techs & set(converter_tech_names)

        #         # Set the commodity demand of this converter subset
        #         upstream_commodity_demand = demand * conversion_ratio
        #         # set setpoints
        #         self.get_setpoints_for_commodity_subset(
        #             inputs,
        #             outputs,
        #             self.commodity,
        #             upstream_commodity_demand,
        #             tech_subset=upstream_techs,
        #         )

        #         pass

        # if demand_converter is None:
        #     # If a converter isnt directly connected to the demand tech, assume its the last one
        #     # TODO: update so that it finds the converter that IS connected to the demand tech
        #     demand_converter = tech
        # work backward from commodity demand
        # tmp = {converter_order[i]:conversion_factors[i] for i in list(conversion_factors.keys())}

        # converter_cnt.reverse()
        # for converter_ii in converter_cnt:
        #     input_cmod, tech, output_cmod = converter_order[converter_ii]
        #     # conversion is input_cmod/output_cmod
        #     tech_ancestors = converter_upstreams[(input_cmod, tech)]
        #     conversion_factors[converter_ii]
        #     upstream_techs = converter_upstreams[(input_cmod, tech)]
        #     upstream_converters = upstream_techs & set(converter_tech_names)
        #     if len(upstream_converters) == 0:
        #         # no converters are upstream
        #         pass
        #     else:
        #         # there are converters upstream
        #         pass

        # {k[0] for i, k in converter_order.items() if k[0] != self.commodity}
