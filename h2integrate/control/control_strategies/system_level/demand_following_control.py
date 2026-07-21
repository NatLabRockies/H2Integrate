import operator
import warnings
import functools
import itertools

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

        self.post_setup_multi_commodity()

    def post_setup_multi_commodity(self):
        if not self.multi_commodity_system:
            return
        converters, converter_upstreams = self.find_converter_techs(include_feedstock_sources=True)
        converter_tech_names = {v[1] for v in list(converters)}
        # 1. Get the nodes of the technology graph that aren't a controllable technology
        non_input_techs = (
            set(self.technology_graph.nodes) - set(self.input_techs) - {self.demand_tech}
        )
        # Group together technologies that are connected to a converter
        # I.e., group together an electrolyzer an hydrogen storage,
        # name this group as the shared commodity with a unique number
        grouped_techs = {f"{k[0][0]}-{i}": k[1] for i, k in enumerate(converter_upstreams.items())}
        # 2. Make a dictionary for future-use that has keys of the technology names and
        # the group they belong to
        reversed_grouped_techs = {}
        for k, v in grouped_techs.items():
            for vv in list(v):
                reversed_grouped_techs[vv] = k

        non_converter_convsion_factors = {}
        # 3. Add in a conversion factor of 1 for all non-converter technologies
        for tc in self.techs_to_commodities:
            t, c = tc
            if t not in converter_tech_names:
                non_converter_convsion_factors[(c, t, c)] = (
                    1.0 if self.config.use_average_conversion_factor else np.ones(self.n_timesteps)
                )

        missing_input_techs = set(self.input_techs) - set(reversed_grouped_techs.keys())
        if missing_input_techs:
            # TODO: check that this works for the normal case
            conversion_factor_add_on, rev_group_add_on = self.get_demand_converter_techs(
                converters, reversed_grouped_techs
            )
            group_tech_add_on = {v: k for k, v in rev_group_add_on.items()}
            for g in list(group_tech_add_on.keys()):
                ts = [k for k, v in rev_group_add_on.items() if v == g]
                group_tech_add_on[g] = set(ts)

            grouped_techs.update(group_tech_add_on)
            non_converter_convsion_factors.update(conversion_factor_add_on)
            reversed_grouped_techs.update(rev_group_add_on)

            converter_upstreams[(self.commodity, self.demand_tech)] = (
                set(rev_group_add_on.keys()) & self.input_techs
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
            non_converter_convsion_factors[(commod, non_t, commod)] = (
                1.0 if self.config.use_average_conversion_factor else np.ones(self.n_timesteps)
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

        self.simple_graph = simple_graph
        self.non_converter_conversion_factors = non_converter_convsion_factors
        self.grouped_techs = grouped_techs
        self.converters = converters
        self.converter_upstreams = converter_upstreams
        self.converter_tech_names = converter_tech_names

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
                if (
                    (conversion_ratio == 0.0)
                    or np.isnan(conversion_ratio)
                    or np.isinf(conversion_ratio)
                ):
                    conversion_ratio = self.get_converter_capacity_conversion_ratio(
                        inputs,
                        input_cmod,
                        output_cmod,
                        tech,
                        list(tech_ancestors),
                    )
            conversion_factors[converter_info] = conversion_ratio
        return conversion_factors

    def convert_combined_conversion_factors_to_tech_demand(
        self,
        grouped_techs,
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
            if tech_to_demand[0] in grouped_techs:
                res = {
                    "techs": list(grouped_techs[tech_to_demand[0]]),
                    "conversion factor": conv_fac,
                }
            else:
                res = {"techs": tech_to_demand[0], "conversion factor": conv_fac}
            # NOTE: could throw this in a function so that the keys are simple if needed
            # below has complicated keys in case theres a more complex architecture
            key = (
                (input_cmod, tech_to_demand[0])
                if use_simple_keynames
                else (input_cmod, tech_to_demand[0], (tech, output_cmod))
            )

            if use_simple_keynames and key in tech_groups_demand:
                run_with_complex_keynames = True
                break
            tech_groups_demand[key] = res
        if run_with_complex_keynames:
            result = self.convert_combined_conversion_factors_to_tech_demand(
                grouped_techs,
                simple_graph,
                grouped_techs_compounding_conversion_factors,
                use_simple_keynames=False,
            )
            return result
        return tech_groups_demand

    def get_demand_converter_techs(self, converters, reversed_grouped_techs):
        missing_input_techs = set(self.input_techs) - set(reversed_grouped_techs.keys())

        # downstream_techs = set()
        # missing_input_tech_commodities = set()
        commodities_out = [self._get_commodity_for_tech(tech) for tech in list(missing_input_techs)]
        commodities_out = set(functools.reduce(operator.iadd, commodities_out, []))
        converter_tech_names = {v[1] for v in list(converters)}
        commodity_in_cmod_out = self.commodity in list(commodities_out)
        if not commodity_in_cmod_out:
            warnings.warn(
                "none of the demand commodities are made by missing techs",
                UserWarning,
                stacklevel=3,
            )

        missing_tech_downstreams = [
            list(nx.descendants(self.technology_graph, tech)) for tech in missing_input_techs
        ]
        missing_tech_downstreams_shared = {self.demand_tech}
        other_converters = converter_tech_names - missing_input_techs

        for downstream in missing_tech_downstreams:
            missing_tech_downstreams_shared = missing_tech_downstreams_shared & set(downstream)
            # TODO: check that no other converters are inbetween
            if set(downstream) & other_converters:
                warnings.warn(
                    "theres an extra converter between the missing techs and the demand",
                    UserWarning,
                    stacklevel=3,
                )
        if not missing_tech_downstreams_shared or len(missing_tech_downstreams_shared) > 1:
            warnings.warn("something unexpected happened", UserWarning, stacklevel=3)

        missing_converter_tech = missing_input_techs & converter_tech_names
        if len(missing_converter_tech) > 1:
            warnings.warn(
                "unsure how code will work with multiple converters connected to demand",
                UserWarning,
                stacklevel=3,
            )
        if not missing_converter_tech:
            warnings.warn("should have a converter before demand ...", UserWarning, stacklevel=3)

        for m0 in list(missing_converter_tech):
            for m1 in list(missing_input_techs - missing_converter_tech):
                m0_upstream = nx.has_path(self.technology_graph, m0, m1)
                m1_upstream = nx.has_path(self.technology_graph, m1, m0)
                if not m0_upstream or m1_upstream:
                    warnings.warn("these technologies arent connected", UserWarning, stacklevel=3)

        # all checks have passed, these techs should be in the same group
        #
        # converter_upstreams[(demand_commodity, self.demand_tech)] = missing_input_techs
        input_comps = {self.demand_tech} - missing_input_techs

        non_input_components = (
            set(functools.reduce(operator.iadd, missing_tech_downstreams, [])) - input_comps
        )
        unique_number = (
            max([int(k.split("-", -1)[-1]) for k in list(reversed_grouped_techs.values())])
        ) + 1
        group_name = f"{self.commodity}-{int(unique_number)}"
        rev_group_add_on = {k: group_name for k in list(non_input_components | missing_input_techs)}
        non_converter_conversion = (
            1.0 if self.config.use_average_conversion_factor else np.ones(self.n_timesteps)
        )
        conversion_factor_add_on = {
            (self.commodity, tech, self.commodity): non_converter_conversion
            for tech in list(missing_input_techs - missing_converter_tech)
        }
        return conversion_factor_add_on, rev_group_add_on

    def compute(self, inputs, outputs):
        if not self.multi_commodity_system:
            self.get_setpoints_for_commodity_subset(
                inputs, outputs, self.commodity, inputs[self.demand_input_name].copy()
            )
            return

        converter_conversion_factors = self.get_conversion_factors(
            self.converters, self.converter_upstreams, inputs
        )

        conversion_factors = (
            self.non_converter_conversion_factors.copy() | converter_conversion_factors
        )

        # 6. Get the compounding conversion factors
        in_degs = dict(self.simple_graph.in_degree)
        starting_techs = {k for k, v in in_degs.items() if v == 0}
        grouped_techs_compounding_conversion_factors = {}
        for starting_tech in list(starting_techs):
            paths = list(nx.all_simple_paths(self.simple_graph, starting_tech, self.demand_tech))
            commodity_graph = nx.DiGraph()  # nodes are commodities

            if len(paths) > 1:
                warnings.warn("There should only be one path", UserWarning, stacklevel=3)
            path = paths[0]
            reverse_path = path[::-1]

            commodity_conversions = [
                self.simple_graph.edges[p0, p1].get("commodity", None)
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
                1.0 if self.config.use_average_conversion_factor else np.ones(self.n_timesteps)
            )

            for edge in commodity_edges:
                # in_cmod is demand of next tech
                out_cmod, in_cmod, tech = edge
                if tech in self.grouped_techs:
                    techs_in_group = list(self.grouped_techs[tech])
                    conversion = (
                        1.0
                        if self.config.use_average_conversion_factor
                        else np.ones(self.n_timesteps)
                    )
                    for t in techs_in_group:
                        if t in self.converter_tech_names:
                            conversion *= conversion_factors[(in_cmod, t, out_cmod)]
                        else:
                            conversion *= conversion_factors[(out_cmod, t, out_cmod)]
                    # TODO: add check if any other non-converter techs have a non-1 conversion factor
                else:
                    conversion = conversion_factors[(in_cmod, tech, out_cmod)]
                path_conversion *= conversion
                grouped_techs_compounding_conversion_factors[(out_cmod, in_cmod, tech)] = (
                    path_conversion
                )

        compounding_conversion_factors = self.convert_combined_conversion_factors_to_tech_demand(
            self.grouped_techs,
            self.simple_graph,
            grouped_techs_compounding_conversion_factors,
            use_simple_keynames=True,
        )
        if any(len(k) > 2 for k in list(compounding_conversion_factors.keys())):
            raise NotImplementedError("This type of system cannot be handled")

        self.tech_demands_set = []
        # Set demand for the techs in the "demand" group
        demand_techs = self.converter_upstreams[(self.commodity, self.demand_tech)]
        outputs = self.get_setpoints_for_commodity_subset(
            inputs,
            outputs,
            self.commodity,
            inputs[self.demand_input_name].copy(),
            tech_subset=demand_techs,
        )

        for cmod_group, cf_techs in compounding_conversion_factors.items():
            commodity, _ = cmod_group

            inputs[self.demand_input_name]
            commodity_demand = inputs[self.demand_input_name].copy() * cf_techs["conversion factor"]

            outputs = self.get_setpoints_for_commodity_subset(
                inputs,
                outputs,
                commodity,
                commodity_demand,
                tech_subset=cf_techs["techs"],
            )
        # NOTE: could add check to make sure everything was set
        unset_techs_cmods = self.techs_to_commodities - set(self.tech_demands_set)
        unset_techs = [k for k in list(unset_techs_cmods) if k[0] not in self.feedstock_comps]
        if unset_techs:
            warnings.warn(
                f"Commands not set for these technologies: {unset_techs}", UserWarning, stacklevel=3
            )
