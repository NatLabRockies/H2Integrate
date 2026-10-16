(slc-base)=
# System Level Control Base Class

The system-level control base class provides a common framework that all controllers (advanced control strategies) can use to configure required inputs and outputs for both the controllers and the components they control or track. This generalization is necessary to implement system-level control in H2I. If the technologies and controllers in a given system were fully specified, this base class would not be needed.

```{important}
SLC demand is supplied by a demand component. When SLC is enabled, only one demand component is currently supported.
```

The base class also abstracts logic that may be shared across different controller types. It includes methods that could be useful, but not all methods will be relevant to every controller you implement.

There are several methods that are already used in the simple controllers that inherit these system.

Setup I/O for SLC controllers.
- `initialize()`
- `setup()`
- `_setup_commodity()`
- `_setup_tech_category()`
- `_setup_feedstock_category()`
- `find_converter_techs()`

Heterogeneous-commodity conversion. These methods let a controller translate demand
for one commodity into demand for the upstream commodities that a converter consumes
to produce it (for example, translating ammonia demand into hydrogen demand across a
synthesis loop, and then into electricity demand across an electrolyzer).
- `detect_commodity_converters()`
    - Module-level helper that identifies converter technologies (technologies whose
      output commodity differs from an input commodity), so demand can propagate backward
      across them.
- `build_dispatch_topology()`
    - Module-level helper, run once at setup, that groups the technology graph into supply
      buses. A supply bus is the set of producers and consumers that share one physical
      stream of a commodity. Producers of the same commodity that are wired to different
      consumers, such as a grid wired only to a Haber-Bosch loop and wind wired only to an
      electrolyzer, are on different buses, so a surplus on one never offsets a deficit on
      the other. It also returns the conversion links between buses, the order in which
      buses are dispatched (demand bus first), and the splitters whose allocation the
      controller sets. It raises an error if the conversions form a cycle, and warns if a
      bus holds a producer that cannot reach every consumer.
- `_build_converters()`
    - Registers each dispatched converter input's `{commodity}_consumed` input from the
      topology's conversion links, and caches the upstream producers of each converter
      input. Conversion ratios are never authored by the user; they are derived
      automatically from measured consumption and from rated capacities.
- `_run_dispatch()`
    - Dispatches each supply bus in the topology's dispatch order, using only the
      producers on that bus, and translates each converter's committed output into demand
      on the bus that supplies its input.
- `_set_splitter_setpoints()`
    - Sets each controller-managed splitter's prescribed priority allocation to the demand
      of the consumers behind its first output.
- `_capacity_ratio()`
    - Returns a scalar input-per-output ratio seeded from rated capacities: the summed
      rated input capacity of a converter's upstream producers divided by the
      converter's rated output capacity. This seeds the conversion ratio on the first
      solver iteration and at zero-output timesteps.
- `_conversion_ratio()`
    - Returns the per-timestep conversion ratio for a converter. It prefers a measured
      ratio computed from the converter's consumed and produced streams, and falls back
      to the capacity-based ratio when a measurement is unavailable.
- `_accumulate_derived_demand()`
    - Adds the demand derived through a converter (output demand times conversion ratio)
      to the upstream commodity's demand, warning only when neither a measured ratio nor
      a capacity-based ratio is available.

Functions for controlling components based on assigned control classifier.
- `_subtract_curtailable()`
- `_dispatch_storage()`
- `find_commodity_suppliers()`

Helper functions for cost-aware controllers.
- `_setup_marginal_costs()`
- `_compute_marginal_costs()`
- `_buy_price_marginal_cost()`
- `_varopex_marginal_cost()`
- `_find_feedstock_techs()`
- `_feedstock_marginal_cost()`

## Base Class and Methods

```{eval-rst}
.. autoclass:: h2integrate.control.control_strategies.system_level.system_level_control_baseclass.SystemLevelControlBase
   :members:
   :undoc-members:
   :show-inheritance:
```
