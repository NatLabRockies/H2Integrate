(slc-base)=
# System Level Control Base Class

The system-level control base class provides a common framework that all controllers (advanced control strategies) can use to configure required inputs and outputs for both the controllers and the components they control or track. This generalization is necessary to implement system-level control in H2I. If the technologies and controllers in a given system were fully specified, this base class would not be needed.

```{important}
SLC demand is supplied by a demand component. When SLC is enabled, only one demand component is currently supported.
```

The base class also abstracts logic that may be shared across different controller types. It includes methods that could be useful, but not all methods will be relevant to every controller you implement.

## Implementation Layout

| Module | Responsibility | Main helpers |
|---|---|---|
| `slc_topology` | Pure setup-time graph analysis. | `find_commodity_suppliers()`, `detect_commodity_converters()`, `build_supply_buses()`, `build_dispatch_topology()` |
| `slc_conversion` | Pure compute-time ratio and demand arithmetic. | `capacity_ratio()`, `measured_ratio()`, `conversion_ratio()`, `accumulate_derived_demand()` |
| `slc_marginal_costs` | Pure buy-price configuration and operating-cost arithmetic. | `buy_price_profile()`, `annualized_marginal_cost()` |
| `system_level_control_baseclass` | OpenMDAO I/O registration, named-input wrappers, and dispatch orchestration. | `setup()`, `_run_dispatch()`, `_dispatch_commodity()`, `_setup_marginal_costs()`, `_compute_marginal_costs()` |

The model and controller share the buy-price configuration helpers in `slc_marginal_costs`.
The base class keeps cost-input registration and feedstock lookup at setup, while delegating
price broadcasting and annualized cost calculations to the pure helpers.

## Heterogeneous-commodity dispatch

All three controllers use the same backward demand walk. They differ only in how they
dispatch controllable producers after fixed production, flexible production, and storage.
The topology is computed at setup; `compute()` builds no graphs and traverses no technology
paths.

### Concepts

| Concept | Meaning |
|---|---|
| **Converter** | A controlled technology that consumes an input commodity and produces a different output commodity, such as an electrolyzer or Haber-Bosch loop. |
| **Supply bus** | One weakly connected component of the graph restricted to a single commodity. Combiners, splitters, and storage can share a bus. Names use the commodity and sorted consumers, for example `electricity:electrolyzer+haber_bosch`. |
| **Conversion link** | A connection from a converter's **output bus to its input bus** for backward demand propagation. It also records the input's physical suppliers. This direction is opposite to physical commodity flow. |
| **Dispatch order** | A lexicographic topological order starting at the demand bus. All downstream contributions arrive before an upstream bus is dispatched. Feedstock-only buses receive no set points. |

`find_commodity_suppliers()` follows only edges carrying the requested commodity, including
paths through splitters and storage. Filtering to controlled technologies and feedstocks
excludes intermediate combiners and transporters from capacity estimates.

```{important}
Demand is tracked **per supply bus, not per commodity**. Wind connected only to an
electrolyzer cannot offset electricity demand on a separate grid-to-Haber-Bosch bus.
```

### Call Trees

The trees separate setup-time graph analysis from compute-time arithmetic. Pure helpers live
in `slc_topology`, `slc_conversion`, and `slc_marginal_costs`.

````{dropdown} Setup: construct topology, register signals, cache suppliers
:open:

```text
H2IntegrateModel._classify_slc_technologies()
  build_dispatch_topology()
    detect_commodity_converters()
    build_supply_buses()
    find_commodity_suppliers()                  -> ConversionLink.suppliers
    lexicographical_topological_sort()          -> dispatch_order; cycles raise
    _warn_if_partial_overlap()
    _find_splitters()                           -> out1 priority consumers
  store slc_topology["dispatch_topology"]
H2IntegrateModel.add_system_level_controller()
  wire production, rated capacity, consumed signals, and splitter set points
  _get_tech_buy_price_input_name()              -> shared price-input identification

SystemLevelControlBase.setup()
  _setup_fixed_category()
  _setup_tech_category()                        -> flexible, dispatchable, storage I/O
    _setup_commodity()
  _setup_feedstock_category()
  reuse dispatch_topology (or build_dispatch_topology() if absent)
  _warn_undispatched_tech_commodities()
  _build_converters()                           -> input registration and link caches
  find_commodity_suppliers()                    -> _storage_suppliers
  add_output()                                 -> splitter set points
CostMinimizationControl.setup() / ProfitMaximizationControl.setup()
  super().setup()                               -> base setup above
  ProfitMaximization only: register commodity_sell_price input
  _setup_marginal_costs()                       -> strategy-specific cost inputs
    _get_buy_price_default_and_shape()          -> technology-compatible price shape
    _get_tech_buy_price_input_name()            -> electricity-specific price units
```
````

````{dropdown} Compute: dispatch buses, propagate committed demand, save trace
:open:

```text
compute()                                      # all three controllers
  _run_dispatch(inputs, outputs)
    reset _converter_contributions and local trace maps
    set every flexible output set point to its rated production
    initialize derived_demand[demand_bus] from the demand input
    for bus in topology.dispatch_order:         # skip if demand never reached it
      snapshot bus_demand[bus]
      _dispatch_commodity(..., producers=bus.producers, is_demand_bus=...)
        _subtract_fixed()                      -> subtract measured fixed output
        _subtract_flexible()                   -> write rated flexible set points
        _dispatch_storage()                    -> write storage set points
        _dispatch_dispatchables()              -> write dispatchable set points
          DemandFollowing: even split
          CostMinimization: _merit_order_dispatch()
          ProfitMaximization: _merit_order_dispatch(), sell-price gate on demand bus
            _compute_marginal_costs()           -> price / VarOpEx / feedstock costs
              _buy_price_marginal_cost() -> buy_price_profile()
              _varopex_marginal_cost() / _feedstock_marginal_cost()
                annualized_marginal_cost()      -> shared cost / annual production
      snapshot bus_residual[bus]
      for link supplying this output bus:
        _accumulate_derived_demand()
          _conversion_ratio()
            _capacity_ratio() -> capacity_ratio()
            conversion_ratio() -> measured_ratio()
          record ratio value and source (or warn once and skip if unavailable)
          accumulate_derived_demand()          -> NEW demand and contribution maps
        assign derived_demand, _converter_contributions from returned maps
    _set_splitter_setpoints()                   -> write priority allocations
    assign dispatch_trace                      -> snapshot for this compute only
```
````

### State Ownership

| State | Written by | Read by / lifetime |
|---|---|---|
| `_dispatch_topology` | Model classification builds it; base `setup()` stores it or builds a standalone fallback. | Model wiring, `_build_converters()`, `_run_dispatch()`, splitter allocation. Reused across computes. |
| OpenMDAO I/O names and units | Category setup helpers and `_build_converters()`. | Dispatch and ratio wrappers. Registered once at setup. |
| `_links_by_out_bus`, `_converter_upstreams`, `_converter_consumed_names` | `_build_converters()`. | Dispatch loop, capacity and measured-ratio wrappers. Setup-time caches. |
| `_storage_suppliers` | Base `setup()`, using `find_commodity_suppliers()`. | `_dispatch_storage()`. No graph traversal during compute. |
| `outputs[*_set_point]` | Flexible pre-pass, flexible/storage/dispatchable steps, then `_set_splitter_setpoints()`. Fixed producers have no commanded set point. | Technology controllers and converter-demand propagation. Set points are commands, not measured production. |
| `derived_demand` | `_run_dispatch()` seeds this local map; the pure accumulator returns replacements assigned by the loop. | Each bus dispatch and the next accumulation. New each compute. |
| `_converter_contributions` | Reset by `_run_dispatch()`; replaced with the pure accumulator's returned map. | Subsequent accumulation, splitter priority allocation, trace snapshot. New each compute. |
| `_missing_ratio_warned` | Initialized by `_build_converters()`; extended by the accumulation wrapper. | Warning suppression across computes, once per conversion triple. |
| `dispatch_trace` | `_run_dispatch()` after splitter allocation; ratio snapshots are collected by the accumulation wrapper. | Debugger or caller inspection. Overwritten, not appended, on each compute. **Not a public API.** |

The pure accumulator mutates neither input map nor its arrays. For one input bus,
contributions from **distinct converters sum**; contributions from multiple outputs of
**one co-product converter combine by element-wise maximum**, avoiding double counting.

### Worked Example: Grid Supplies Only Haber-Bosch

This small `DemandFollowingControl` case uses four identical timesteps. It is separate
from the shared-electricity-bus example linked in {ref}`slc-demand-following`.

```text
wind --electricity--> electrolyzer --hydrogen--> haber_bosch --ammonia--> ammonia_demand
grid ----------------electricity--------------> haber_bosch
n2_feedstock --------nitrogen-----------------> haber_bosch
```

| Input | Value at each timestep |
|---|---|
| Ammonia demand | 100 kg/h |
| Rated wind / grid | 1500 / 500 kW |
| Rated electrolyzer / Haber-Bosch | 40 kg/h hydrogen / 1000 kg/h ammonia |
| Available wind production | 1200 kW |
| Measured Haber-Bosch output / consumption | 100 kg/h ammonia; 18 kg/h hydrogen; 50 kW electricity |
| Measured electrolyzer output / consumption | 18 kg/h hydrogen; 990 kW electricity |

#### Inspect the Topology

The pure setup helper can be used without constructing an OpenMDAO problem:

```python
from h2integrate.core.connection_utils import create_technology_graph
from h2integrate.control.control_strategies.system_level.slc_topology import (
    build_dispatch_topology,
)

connections = [
    ["wind", "electrolyzer", "electricity", "cable"],
    ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
    ["grid", "haber_bosch", "electricity", "cable"],
    ["n2_feedstock", "haber_bosch", "nitrogen", "pipe"],
    ["haber_bosch", "ammonia_demand", "ammonia", "pipe"],
]
classifiers = {
    "wind": "flexible",
    "grid": "dispatchable",
    "electrolyzer": "dispatchable",
    "haber_bosch": "dispatchable",
    "n2_feedstock": "feedstock",
    "ammonia_demand": "demand",
}
produced = {
    ("wind", "electricity"),
    ("grid", "electricity"),
    ("electrolyzer", "hydrogen"),
    ("haber_bosch", "ammonia"),
    ("n2_feedstock", "nitrogen"),
}
topology = build_dispatch_topology(
    create_technology_graph(connections), classifiers, produced, "ammonia_demand", "ammonia"
)
print(topology.describe())
```

```text
Demand bus: ammonia:ammonia_demand
Dispatch order:
  1. ammonia:ammonia_demand (producers: haber_bosch; consumers: ammonia_demand)
  2. electricity:haber_bosch (producers: grid; consumers: haber_bosch)
  3. hydrogen:haber_bosch (producers: electrolyzer; consumers: haber_bosch)
  4. electricity:electrolyzer (producers: wind; consumers: electrolyzer)
Not dispatched: nitrogen:haber_bosch
Conversion links (output bus -> input bus):
  electrolyzer: hydrogen:haber_bosch -> electricity:electrolyzer
  haber_bosch: ammonia:ammonia_demand -> electricity:haber_bosch
  haber_bosch: ammonia:ammonia_demand -> hydrogen:haber_bosch
```

#### Follow the Demand

Ratios are measured **input per output**: 0.5 kWh/kg ammonia, 0.18 kg hydrogen/kg
ammonia, and 55 kWh/kg hydrogen. Each link multiplies the converter's committed output
set point, not the original plant demand.

| Step | Dispatched bus | Demand in | Set point written | New upstream demand and contribution |
|---|---|---|---|---|
| 1 | `ammonia:ammonia_demand` | 100 kg/h | Haber-Bosch: 100 kg/h | Electricity: `100 * 0.5 = 50` kW; hydrogen: `100 * 0.18 = 18` kg/h, both attributed to `haber_bosch`. |
| 2 | `electricity:haber_bosch` | 50 kW | Grid: 50 kW | None. |
| 3 | `hydrogen:haber_bosch` | 18 kg/h | Electrolyzer: 18 kg/h | Electricity: `18 * 55 = 990` kW, attributed to `electrolyzer`. |
| 4 | `electricity:electrolyzer` | 990 kW | Wind: 1500 kW (rated) | None; available wind is 1200 kW, leaving a 210 kW surplus. |

After step 1, `derived_demand` contains the ammonia, grid-electricity, and hydrogen
entries. Step 3 adds electrolyzer electricity. Dispatching a bus does not remove its
entry. Nitrogen is present in the topology but not propagated: its bus has only a
feedstock producer.

Pooling electricity would incorrectly subtract 1200 kW wind from `50 + 990 = 1040` kW
and command zero grid supply. Separate buses preserve the required **50 kW grid command**.

````{dropdown} Inspect the final dispatch trace

After running the model, inspect `model.plant.system_level_controller.dispatch_trace`
for an `H2IntegrateModel` instance named `model`. The Appendix A unit test checks the
complete trace below. For readability, each array is shown as a four-element list.

```python
{
    "dispatch_order": (
        "ammonia:ammonia_demand",
        "electricity:haber_bosch",
        "hydrogen:haber_bosch",
        "electricity:electrolyzer",
    ),
    "bus_demand": {
        "ammonia:ammonia_demand": [100.0] * 4,
        "electricity:haber_bosch": [50.0] * 4,
        "hydrogen:haber_bosch": [18.0] * 4,
        "electricity:electrolyzer": [990.0] * 4,
    },
    "bus_residual": {
        "ammonia:ammonia_demand": [0.0] * 4,
        "electricity:haber_bosch": [0.0] * 4,
        "hydrogen:haber_bosch": [0.0] * 4,
        "electricity:electrolyzer": [0.0] * 4,
    },
    "ratios": {
        ("electricity", "haber_bosch", "ammonia"): {
            "value": [0.5] * 4, "source": ["measured"] * 4,
        },
        ("hydrogen", "haber_bosch", "ammonia"): {
            "value": [0.18] * 4, "source": ["measured"] * 4,
        },
        ("electricity", "electrolyzer", "hydrogen"): {
            "value": [55.0] * 4, "source": ["measured"] * 4,
        },
    },
    "contributions": {
        "electricity:haber_bosch": {"haber_bosch": [50.0] * 4},
        "hydrogen:haber_bosch": {"haber_bosch": [18.0] * 4},
        "electricity:electrolyzer": {"electrolyzer": [990.0] * 4},
    },
}
```
````

```{note}
`bus_residual` is unmet **commanded** demand after dispatch, not a plant mass/energy-balance
check. Surplus is floored at zero before dispatchables, so the wind bus records zero,
not -210 kW. A zero residual does not guarantee the physical models delivered their commands.
```

### Ratios and Limitations

```{important} The capacity seed is a sizing estimate, not an efficiency
The seed divides the summed rated capacities of the converter's physical input suppliers
by its rated output. Feedstocks contribute their mean supply instead of a rated capacity.
Valid, finite consumption/output measurements with nonzero output take precedence per
timestep. The seed is used before measurements exist and at invalid or zero-output points;
an unconnected standalone consumption input uses it throughout.
```

For this example, the capacity-only estimates are `500 / 1000 = 0.5` for Haber-Bosch
electricity, `40 / 1000 = 0.04` for hydrogen, and `1500 / 40 = 37.5` for electrolyzer
electricity. They produce demands of 50 kW, 4 kg/h hydrogen, and 150 kW, respectively.
The measured chain instead requires `100 * 0.18 * 55 = 990` kW. The backward walk gives
the same ratio product as a conversion recipe, while accounting for the set points
committed after downstream dispatch.

- **No capacity seed:** if some measurements are valid, their mean fills invalid points
  and the source label remains `measured`. If neither a seed nor valid measurements exists,
  the wrapper warns once per conversion triple and skips propagation along that link.
- **Partial overlap:** a bus is dispatched as one pool. Setup warns when a controlled producer
  cannot reach every consumer on that bus; physical flow allocation is not solved here.
- **Cycles:** a conversion cycle reachable from the demand bus raises `ValueError` at setup,
  naming the buses and converter technologies. A separate downstream fuel-cell bus can be acyclic.
- **Connection order:** splitter out1 follows the first outgoing connection and receives
  priority. This is the only intentional connection-order dependence; preserve that pair's
  order when rearranging connections.
- **Model interface:** the current model wiring requires `{input_commodity}_consumed` outputs
  for dispatched converter inputs and `prescribed_commodity` mode for controlled splitters.
  The standalone NaN fallback does not guard a missing output in full-model wiring.
- **Scope:** one demand component is supported. Multiple-storage allocation and flow-based
  optimization of partially overlapping buses are not addressed by this backward walk.

## Topology and Conversion Reference

These pure helpers separate setup-time graph analysis from compute-time ratio and demand
arithmetic. The base class below owns OpenMDAO I/O and orchestration.

```{eval-rst}
.. autoclass:: h2integrate.control.control_strategies.system_level.slc_topology.SupplyBus
   :noindex:

.. autoclass:: h2integrate.control.control_strategies.system_level.slc_topology.ConversionLink
   :noindex:

.. autoclass:: h2integrate.control.control_strategies.system_level.slc_topology.SplitterNode
   :noindex:

.. autoclass:: h2integrate.control.control_strategies.system_level.slc_topology.DispatchTopology
   :members: describe, dispatch_links, consumption_signals
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_topology.find_commodity_suppliers
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_topology.detect_commodity_converters
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_topology.build_supply_buses
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_topology.build_dispatch_topology
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_conversion.capacity_ratio
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_conversion.measured_ratio
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_conversion.conversion_ratio
   :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_conversion.accumulate_derived_demand
   :noindex:
```

## Base Class and Methods

### Marginal-Cost Helpers

```{eval-rst}
.. autofunction:: h2integrate.control.control_strategies.system_level.slc_marginal_costs.buy_price_profile
  :noindex:

.. autofunction:: h2integrate.control.control_strategies.system_level.slc_marginal_costs.annualized_marginal_cost
  :noindex:
```

### OpenMDAO Orchestration

```{eval-rst}
.. autoclass:: h2integrate.control.control_strategies.system_level.system_level_control_baseclass.SystemLevelControlBase
   :members:
   :undoc-members:
   :show-inheritance:
```
