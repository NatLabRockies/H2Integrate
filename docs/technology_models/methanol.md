# Methanol model

Methanol is an essential precursor to many chemicals, and is also used as a fuel, especially in marine applications. It can be produced from many substances, which the most conventional route using natural gas as the main feedstock, and other developing technologies that combine hydrogen and carbon dioxide (CO2). A basic framework for modeling methanol production is set up in `h2integrate/converters/methanol/methanol_baseclass.py`, and specific technologies are modeled in inherited classes. Examples of each methanol production method can be found in `examples/03_methanol`. Currently, H2I models two methanol production technologies:

1. Steam Methane Reforming (SMR): This is the most prominent commercial production route for methanol in the United States, and utilizes natural gas as the main feedstock. This model is found at `h2integrate/converters/methanol/smr_methanol_plant.py`. The NLR modeling of this process is based on an [NETL Baseline Analysis of Crude Methanol Production from Coal and Natural Gas](https://doi.org/10.2172/1601964).

2. CO2 Hydrogenation: This is a developing methanol production technology that directly combines hydrogen with carbon dioxide to produce methanol. This model is found at `h2integrate/converters/methanol/co2h_methanol_plant.py`. The NLR modeling of this process is based on a combination of three peer-reviewed studies:
    - [Perez-Fortes et al.](https://doi.org/10.1016/j.apenergy.2015.07.067)
    - [Szima et al.](https://doi.org/10.1016/j.jcou.2018.02.007)
    - [Nyari et al.](https://doi.org/10.1016/j.jcou.2020.101166)

This modeling is further documented in a journal publication by [Martin et al.](https://doi.org/10.1021/acs.est.4c02589)

## Registered models and configuration

| Route | Performance model | Cost model | Finance model |
|---|---|---|---|
| Steam methane reforming | {py:class}`~h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantPerformanceModel` | {py:class}`~h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantCostModel` | {py:class}`~h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantFinanceModel` |
| CO2 hydrogenation | {py:class}`~h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantPerformanceModel` | {py:class}`~h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantCostModel` | {py:class}`~h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantFinanceModel` |

Both performance models use hourly time steps and ratio-based feedstock calculations, limited by
the configured `plant_capacity_kgpy` and available inputs. The SMR route consumes natural gas and
produces electricity as a co-product. The CO2 hydrogenation route consumes hydrogen, carbon
dioxide, natural gas, and electricity. Both report methanol production and feedstock consumption.
The cost models use total overnight, fixed operating, and variable operating cost
inputs, then calculate route-specific feedstock costs and credits. The finance models report
levelized cost of methanol.

The performance models divide `plant_capacity_kgpy` by the number of simulated time steps to
set the hourly production limit, then scale total simulated production to an annual value.
They declare `input_capacity_factor`, `co2e_emissions`, and `h2o_consumption`, but their compute
methods do not use the former or assign the latter two outputs. The CO2 hydrogenation performance
output is named `co2_consume`, whereas its cost input is `carbon_dioxide_consume`; connect them
explicitly. Its `hydrogen_consume` is declared in kg/s even though the calculation uses the kg/h
input profile.

Configuration API references:

- {py:class}`~h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantPerformanceModelConfig`
- {py:class}`~h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantCostModelConfig`
- {py:class}`~h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantFinanceModelConfig`
- {py:class}`~h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantPerformanceModelConfig`
- {py:class}`~h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantCostModelConfig`
- {py:class}`~h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantFinanceModelConfig`

```{eval-rst}
.. autoclass:: h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantPerformanceModelConfig
    :members:
    :no-index:

.. autoclass:: h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantCostModelConfig
    :members:
    :no-index:

.. autoclass:: h2integrate.converters.methanol.smr_methanol_plant.SMRMethanolPlantFinanceModelConfig
    :members:
    :no-index:

.. autoclass:: h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantPerformanceModelConfig
    :members:
    :no-index:

.. autoclass:: h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantCostModelConfig
    :members:
    :no-index:

.. autoclass:: h2integrate.converters.methanol.co2h_methanol_plant.CO2HMethanolPlantFinanceModelConfig
    :members:
    :no-index:
```
