# Steel Electric Arc Furnace Models

H2I contains two steel electric arc furnace (EAF) models, one is for a facility that utilizes iron pellets from natural gas (NG) direct iron reduction and another facility that utilizes iron pellets from hydrogen (H2)direct iron reduction.

The main difference is the required feedstocks for processing the pellets.
- NG-EAF requires: natural gas, water, sponge iron and electricity.
- H2-EAF requires: natural gas, water, carbon, lime, sponge iron and electricity.


The original models were constructed in Aspen Pro and translated into Python and added to H2I. The models were developed in conjunction with [Lawrence Berkeley National Laboratory (LBNL)](https://www.lbl.gov/).

The models implemented in H2I are:
- Natural gas direct-reduction route:
  {py:class}`~h2integrate.converters.steel.steel_eaf_plant.NaturalGasEAFPlantPerformanceComponent`
  and {py:class}`~h2integrate.converters.steel.steel_eaf_plant.NaturalGasEAFPlantCostComponent`.
- Hydrogen direct-reduction route:
  {py:class}`~h2integrate.converters.steel.steel_eaf_plant.HydrogenEAFPlantPerformanceComponent`
  and {py:class}`~h2integrate.converters.steel.steel_eaf_plant.HydrogenEAFPlantCostComponent`.

Both routes use
{py:class}`~h2integrate.converters.steel.steel_eaf_baseclass.ElectricArcFurnacePerformanceBaseConfig`
and {py:class}`~h2integrate.converters.steel.steel_eaf_baseclass.ElectricArcFurnaceCostBaseConfig`.
The performance components take `steel_command_value`, `system_capacity`, and the feedstock
profiles above, and report `steel_out`, consumption, and production summaries. The cost components
report `CapEx`, fixed `OpEx`, and `VarOpEx`. All require one-hour time steps.

## Simple steel plant

The separate {py:class}`~h2integrate.converters.steel.steel.SteelPerformanceModel` represents
steel production using a configured plant capacity and capacity factor.
{py:class}`~h2integrate.converters.steel.steel.SteelCostAndFinancialModel` calculates capital and operating costs
and reports levelized cost of steel (`LCOS`). Both use hourly time steps. These models are distinct
from the natural-gas and hydrogen EAF performance components described above.

The simple performance model uses `electricity_in` only to determine the profile length, not to
limit production. It distributes configured annual production over the simulated time steps,
then annualizes the resulting total; partial-year simulations therefore require care.

See {py:class}`~h2integrate.converters.steel.steel.SteelPerformanceModelConfig` and
{py:class}`~h2integrate.converters.steel.steel.SteelCostAndFinancialModelConfig` for the
simple models' configuration APIs.

```{eval-rst}
.. autoclass:: h2integrate.converters.steel.steel.SteelPerformanceModelConfig
  :members:
  :no-index:

.. autoclass:: h2integrate.converters.steel.steel.SteelCostAndFinancialModelConfig
  :members:
  :no-index:
```

```{note}
The EAF model use sponge iron as an input rather than pig iron, which is lower in carbon content. The LBNL model calls the input to the EAF pig iron, but that's typically produced using a blast furnace rather than through the DRI process and has higher carbon impurities.
```

Citation:
```bibtex
@article{rosner2023green,
  title={Green steel: design and cost analysis of hydrogen-based direct iron reduction},
  author={Rosner, Fabian and Papadias, Dionissios and Brooks, Kriston and Yoro, Kelvin and Ahluwalia, Rajesh and Autrey, Tom and Breunig, Hanna},
  journal={Energy \& Environmental Science},
  volume={16},
  number={10},
  pages={4121--4134},
  year={2023},
  publisher={Royal Society of Chemistry}
}
```
