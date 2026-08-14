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
      output commodity differs from an input commodity) that have a controllable
      producer for that input commodity, so demand can propagate backward across them.
- `_build_conversion_ratios()`
    - Registers each converter's `{commodity}_consumed` inputs and reads any static
      conversion ratios supplied under
      `technologies.<tech>.model_inputs.control_parameters.conversion_ratios`.
- `_conversion_ratio()`
    - Returns the per-timestep conversion ratio for a converter. It prefers a measured
      ratio computed from the converter's consumed and produced streams, and falls back
      to the static ratio from the technology config when a measurement is unavailable.
- `_accumulate_derived_demand()`
    - Adds the demand derived through a converter (output demand times conversion ratio)
      to the upstream commodity's demand, warning only when neither a measured nor a
      static ratio is available.

Functions for controlling components based on assigned control classifier.
- `_subtract_curtailable()`
- `_dispatch_storage()`
- `get_upstream_techs_for_commodity()`

Helper functions for cost-aware controllers.
- `_setup_marginal_costs()`
- `_compute_marginal_costs()`
- `_buy_price_marginal_cost()`
- `_varopex_marginal_cost()`
- `_find_feedstock_techs()`
- `_feedstock_marginal_cost()`

## Base Class and Methods

```{eval-rst}
.. autoclass:: h2integrate.control.control_strategies.system_level.system_level_control_base.SystemLevelControlBase
   :members:
   :undoc-members:
   :show-inheritance:
```
