# Nuclear power plant models

H2Integrate currently includes two nuclear converter options:

- `QuinnNuclearPerformanceModel` with `QuinnNuclearCostModel` for an electricity-only nuclear plant, based on Quinn et al. (2023)
- `SimpleThermalNuclearReactorPerformanceModel` with `SimpleThermalNuclearReactorCostModel` for a thermal reactor that can trade off electricity production and process heat delivery. This is a simplified thermal reactor representation intended for coupled workflows such as nuclear plus a high-temp steam electrolyzer (HTSE).

## Quinn electricity-only nuclear model

Use this model by setting:

- performance model: `QuinnNuclearPerformanceModel`
- cost model: `QuinnNuclearCostModel`

This model produces electricity only and clips commanded output to rated plant capacity.
It accepts `electricity_command_value` and `system_capacity` in kW, and reports
`electricity_out`, total and annual production, and capacity factor. The cost model uses
capacity and the electricity profile to calculate `CapEx`, fixed `OpEx`, and `VarOpEx`;
the variable cost is based on simulated-period production and is repeated over plant life
without annualization. Both models require one-hour time steps.

### API details
See {py:class}`~h2integrate.converters.nuclear.nuclear_plant.QuinnNuclearPerformanceModel` and
{py:class}`~h2integrate.converters.nuclear.nuclear_plant.QuinnNuclearPerformanceModelConfig`,
and {py:class}`~h2integrate.converters.nuclear.nuclear_plant.QuinnNuclearCostModel` and
{py:class}`~h2integrate.converters.nuclear.nuclear_plant.QuinnNuclearCostModelConfig`.

```{eval-rst}
.. autoclass:: h2integrate.converters.nuclear.nuclear_plant.QuinnNuclearPerformanceModelConfig
   :no-members:
   :no-index:

.. autoclass:: h2integrate.converters.nuclear.nuclear_plant.QuinnNuclearCostModelConfig
   :no-members:
   :no-index:
```

(references)=
### References
- Quinn, J. et al., 2023. Small modular reactor light water reactor techno-economic analysis. Applied Energy 120669. https://doi.org/10.1016/j.apenergy.2023.120669

## Simple thermal nuclear reactor model

You can use this model by setting (in your `tech_config.yaml`):

- performance model: `SimpleThermalNuclearReactorPerformanceModel`
- cost model: `SimpleThermalNuclearReactorCostModel`

This model represents a reactor with:

- a high-pressure electric conversion stage
- a low-pressure electric conversion stage
- an extractable process heat stream, extracted upstream of the low-pressure turbine stages (dashed red arrow in the figure)

The model was developed to provide both heat and electricity for high-temperature steam
electrolysis as modeled in [HTSEPerformanceModel](h2_htse.md). The integrated thermal-nuclear
and HTSE system is shown in the figure below. The models can also integrate with other technologies.

```{figure} images/nuclear_htse_system_diagram.png
:alt: System diagram showing a thermal nuclear reactor with integrated high-temperature steam electrolysis.
:width: 100%
:align: center
```

It supports two operating modes:

- `heat`: In `heat` mode, delivered heat is limited by available process heat and requested heat demand. Remaining low-pressure heat is converted to electricity.

- `electricity`: In `electricity` mode, electricity is limited by the command value and rated capacity. Remaining process heat is then outputted as `heat_out`.

```{figure} images/ThermalNucReactor-H2I.png
:alt: Thermal nuclear reactor schematic
:width: 100%
:align: center
```

### Thermal reactor dispatch logic

The model computes a combined electric efficiency:

$$
\eta_{combined} = \eta_{hp} + (1 - \eta_{hp}) \eta_{lp}
$$

Then infers thermal capacity from rated electrical capacity:

$$
P_{thermal} = \frac{P_{electric,rated}}{\eta_{combined}}
$$

### API details
See
{py:class}`~h2integrate.converters.nuclear.nuclear_plant_thermal.SimpleThermalNuclearReactorPerformanceModel`
and
{py:class}`~h2integrate.converters.nuclear.nuclear_plant_thermal.SimpleThermalNuclearReactorPerformanceModelConfig`,
and
{py:class}`~h2integrate.converters.nuclear.nuclear_plant_thermal.SimpleThermalNuclearReactorCostModel`
and
{py:class}`~h2integrate.converters.nuclear.nuclear_plant_thermal.SimpleThermalNuclearReactorCostModelConfig`.

The performance model declares its electrical and thermal power inputs and outputs in MW,
including `electricity_command_value`, `heat_command_value`, `electricity_out`, and `heat_out`.
Its cost model declares `rated_capacity` in MW and unit costs in USD/MW, USD/(MW year), and
USD/(MW h), but declares `electricity_out` in kW. The cost calculation currently multiplies the
kW profile directly by the per-MWh variable cost before annualizing it; account for this unit
inconsistency when interpreting `VarOpEx`. Both components require one-hour time steps.

```{eval-rst}
.. autoclass:: h2integrate.converters.nuclear.nuclear_plant_thermal.SimpleThermalNuclearReactorPerformanceModelConfig
   :no-members:
   :no-index:

.. autoclass:: h2integrate.converters.nuclear.nuclear_plant_thermal.SimpleThermalNuclearReactorCostModelConfig
   :no-members:
   :no-index:
```

## Integrated nuclear and HTSE example

[Example 36: Nuclear Reactor and HTSE](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/36_nuclear_reactor_htse)
connects thermal nuclear output to the high-temperature steam electrolyzer.
