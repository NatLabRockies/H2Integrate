# Direct Reduced Iron Models

H2I contains two direct reduced iron (DRI) models, one is for a facility run using natural gas and another facility run using hydrogen.

The original models were constructed in Aspen Pro and translated into Python and added to H2I. The models were developed in conjunction with [Lawrence Berkeley National Laboratory (LBNL)](https://www.lbl.gov/).

The models implemented in H2I are:
- Natural Gas Electric Arc Furnace
  - `NaturalGasIronReductionPlantPerformanceComponent`
  - `NaturalGasIronReductionPlantCostComponent`
- Hydrogen Electric Arc Furnace
  - `HydrogenIronReductionPlantPerformanceComponent`
  - `HydrogenIronReductionPlantCostComponent`

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
