# Ammonia model

Ammonia is a common fertilizer, and also has the potential to serve as a lower-cost form of hydrogen storage than compressed hydrogen gas. This is typically an energy-intensive process, with the ammonia reactor requiring electricity connected from an electric generator. The primary inputs are hydrogen and air, with the air fed into an air separator to produce nitrogen in an intermediate step, and oxygen as a co-product that is sold to offset opex costs. The ammonia synthesis is highly exothermic, and future versions of this model are planned to connect the generated heat (in the form of steam) to other converters requiring thermal energy as an input. Currently, H2I has two ammonia production models:

1. The 'Simple' Ammonia Model: A model that only uses the ratios of feedstocks to ammonia output as performance parameters. This model is found at `h2integrate/converters/ammonia/simple_ammonia_model.py`. This model is based off of ASPEN modeling performed at Argonne National Lab (ANL) by [Lee et al.](https:/doi.org/10.1039/d2gc00843b), and was orginally developed for H2I by [Reznicek et al.](https://doi.org/10.1016/j.crsus.2025.100338). The cost modeling in this model directly follows the two above studies. One of the plants included in the Reznicek et al study is shown in the example `examples/02_texas_ammonia/`.

2. The Synloop Ammonia Model: This model allows direct stream table measurements (or modeled values) from an ammonia synthesis loop to be used as performance parameters. The cost parameters are largely the same as the simple ammonia model. This model is found at `h2integrate/converters/ammonia/ammonia_synloop.py`. The example in `examples/12_ammonia_synloop/` uses mostly the same parameters as those used by Reznicek et al., but with updated capex values for the air separator and synthesis loop derived from an NETL baseline study of ammonia production by [Brasington et al.](https://doi.org/10.2172/1515254)

## Synloop purge gas output

The Synloop Ammonia Model exposes the purge gas exiting the synthesis loop as a **multivariable stream** called `process_gas_mixture`. This is a general-purpose stream type for process gas mixtures that can be reused by other components. It bundles seven constituent variables into a single connection type:

| Variable | Units | Description |
|---|---|---|
| `mass_flow` | kg/h | Total gas mass flow rate |
| `hydrogen_mass_fraction` | unitless | Mass fraction of hydrogen in the gas stream |
| `nitrogen_mass_fraction` | unitless | Mass fraction of nitrogen in the gas stream |
| `argon_mass_fraction` | unitless | Mass fraction of argon in the gas stream |
| `ammonia_mass_fraction` | unitless | Mass fraction of ammonia in the gas stream |
| `temperature` | K | Gas stream temperature |
| `pressure` | bar | Gas stream pressure |

The purge gas composition is determined by the `purge_gas_x_h2`, `purge_gas_x_n2`, `purge_gas_x_ar`, and `purge_gas_x_nh3` molar fractions in the performance config, which are converted to mass fractions using the molecular weights of all species. The total purge gas mass flow is `purge_gas_mass_ratio × ammonia_produced`.

The `hydrogen_out` and `nitrogen_out` outputs of the synloop model represent only the **unused feedstock** that was available but not consumed. Purge gas hydrogen and nitrogen are reported separately through the `process_gas_mixture` stream. This separation allows downstream components (such as a hydrogen recovery unit or a recycle loop) to receive the purge gas as a distinct physical stream with its own temperature, pressure, and composition.

To connect the purge gas to a downstream consumer at the plant level, add a single interconnection line:

```yaml
technology_interconnections:
  - [ammonia, purge_gas_consumer, process_gas_mixture]
```

The framework handles connecting all constituent variables automatically. See `examples/32_multivariable_streams/` for a general example of multivariable stream connections.
