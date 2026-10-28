# Direct Reduced Iron Models

H2I contains two direct reduced iron (DRI) models, one is for a facility run using natural gas and another facility run using hydrogen.

The original models were constructed in Aspen Pro and translated into Python and added to H2I. The models were developed in conjunction with [Lawrence Berkeley National Laboratory (LBNL)](https://www.lbl.gov/).

The models implemented in H2I are:
- Natural gas direct reduction:
  {py:class}`~h2integrate.converters.iron.iron_dri_plant.NaturalGasIronReductionPlantPerformanceComponent`
  and {py:class}`~h2integrate.converters.iron.iron_dri_plant.NaturalGasIronReductionPlantCostComponent`.
- Hydrogen direct reduction:
  {py:class}`~h2integrate.converters.iron.iron_dri_plant.HydrogenIronReductionPlantPerformanceComponent`
  and {py:class}`~h2integrate.converters.iron.iron_dri_plant.HydrogenIronReductionPlantCostComponent`.

Both routes use
{py:class}`~h2integrate.converters.iron.iron_dri_baseclass.IronReductionPerformanceBaseConfig`
and {py:class}`~h2integrate.converters.iron.iron_dri_baseclass.IronReductionCostBaseConfig`.
The performance model takes a `sponge_iron_command_value`, a rated `system_capacity`, and
route-specific `*_in` feedstocks. It reports `sponge_iron_out`, feedstock consumption, and
production summaries. The cost model uses the plant capacity and cost coefficients to report
`CapEx`, fixed `OpEx`, and `VarOpEx`. Both components require one-hour time steps.

```{note}
The DRI model outputs sponge iron, which is low in carbon content. The LBNL model calls the outputs pig iron, but that's typically produced using a blast furnace rather than through the DRI process and has higher carbon impurities.
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
