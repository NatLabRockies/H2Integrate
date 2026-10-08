# PEM Electrolyzer

H2Integrate's `ECOElectrolyzerPerformanceModel` wraps the ECO-PEM model to convert electricity
into hydrogen and oxygen. It models electrolyzer clusters, turndown, degradation, and replacement
timing. Use it when an analysis needs an electrolyzer model with time-varying operation rather than
a fixed-rate conversion.

## Registered models

- `ECOElectrolyzerPerformanceModel` computes hydrogen and oxygen production, electricity and water
  consumption, capacity factor, and the replacement schedule.
- `BasicElectrolyzerCostModel`, `SingliticoCostModel`, and `CustomElectrolyzerCostModel` provide
  alternative capital-cost models. Choose the cost model whose assumptions and input data fit the
  analysis; their configuration classes are documented below.

The performance model requires a one-hour time step. `size_mode: normal` uses the configured
cluster count and rating. `resize_by_max_feedstock` can size from the maximum available electricity,
and `resize_by_max_commodity` can size from a connected hydrogen demand. The resize modes also
require `flow_used_for_sizing`; see [Sizing Modes](../user_guide/run_size_modes.md) for the
framework-level behavior.

## Configuration

The performance configuration controls cluster count and rating, onshore/offshore location,
turndown, degradation penalties, and operating hours to end of life. Cost inputs depend on the
selected cost model.

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.pem_electrolyzer.ECOElectrolyzerPerformanceModelConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.hydrogen.basic_cost_model.BasicElectrolyzerCostModelConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.hydrogen.singlitico_cost_model.SingliticoCostModelConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.hydrogen.custom_electrolyzer_cost_model.CustomElectrolyzerCostModelConfig
   :members:
   :no-index:
```

## Examples

- [Example 25: Sizing Modes](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/25_sizing_modes)
  demonstrates the electrolyzer's sizing modes.
- [Example 01: Onshore Steel](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/01_onshore_steel_mn)
  and [Example 13: Dispatch for Electrolyzer](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/13_dispatch_for_electrolyzer)
  show the model in larger systems.

The separate [WOMBAT electrolyzer operations model](wombat_electrolyzer_om.md) can be used when
maintenance and downtime behavior are important.
