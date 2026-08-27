# Nuclear power plant models

H2Integrate currently includes two nuclear converter options:

- `QuinnNuclearPerformanceModel` with `QuinnNuclearCostModel` for an electricity-only nuclear plant, based on Quinn et al. (2023)
- `SimpleThermalNuclearReactorPerformanceModel` with `SimpleThermalNuclearReactorCostModel` for a thermal reactor that can trade off electricity production and process heat delivery. This is a simplified thermal reactor representation intended for coupled workflows such as nuclear plus a high-temp steam electrolyzer (HTSE).

## Quinn electricity-only nuclear model

Use this model by setting:

- performance model: `QuinnNuclearPerformanceModel`
- cost model: `QuinnNuclearCostModel`

This model produces electricity only and clips commanded output to rated plant capacity.

### API details
For API details, see the [`QuinnNuclearPerformanceModel` and `QuinnNuclearCostModel` API documentation](../_autosummary/h2integrate.converters.nuclear.nuclear_plant).

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

The model was developed to provide both heat and electricity for high-temperature steam electrolysis as modeled in `HTSEPerformanceModel` and `HTSEPerformanceModel`. The integrated thermal-nuclear and HTSE system is shown in the figure below. However, the models were implemented in such a way as to allow integration with other technologies.

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
For API details, see the [`SimpleThermalNuclearReactorPerformanceModel` and `SimpleThermalNuclearReactorCostModel` API documentation](../_autosummary/h2integrate.converters.nuclear.nuclear_plant_thermal).
