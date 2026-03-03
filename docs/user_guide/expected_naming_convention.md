# Expected Technology Naming Convention in H2I

Some logic within H2I relies on expected naming conventions of technologies in the technology configuration file. The following details the naming convention required for H2I to run properly.

```yaml
technologies:
    tech_name_A: #these are the keys with specific required naming convention
        performance_model:
            model:
        cost_model:
            model:
        model_inputs:
            performance_parameters:
```

- if using the `GenericCombinerPerformanceModel` as the technology performance model, the technology name must include the name `combiner`. Some examples of valid technology names are:
    + 'combiner'
    + 'combiner_1'
    + 'electricity_combiner'
    + 'hydrogen_combiner_2'
- if using the `GenericSplitterPerformanceModel` as the technology performance model, the technology name must include the name `splitter`. Some examples of valid technology names are:
    + 'splitter'
    + 'splitter_1'
    + 'electricity_splitter'
    + 'hydrogen_splitter_2'
- if using the `FeedstockPerformanceModel` as the technology performance model and the `FeedstockCostModel` as the technology cost model, the technology name must include the name `feedstock`. Some examples of valid technology names are:
    + 'feedstock'
    + 'water_feedstock'
    + 'feedstock_iron_ore'
    + 'natural_gas_feedstock_tank'
- If a transport component is defined in the technology configuration file (most likely to transport commodities that cannot be transported by 'pipe' or 'cable'), the technology name must include the name `transport`. Some examples of valid technology names are:
    + 'transport'
    + 'lime_transport'
    + 'transport_iron_ore'
    + 'reformer_catalyst_transport_tube'

```{note}
These naming convention limitations are known and you can track them in this issue: https://github.com/NatLabRockies/H2Integrate/issues/374
```
