# Steel Electric Arc Furnace Models

H2I contains two steel electric arc furnace (EAF) models, one is for a facility that utilizes iron pellets from natural gas (NG) direct iron reduction and another facility that utilizes iron pellets from hydrogen (H2)direct iron reduction.

The main difference is the required feedstocks for processing the pellets.
- NG-EAF requires: natural gas, water, pig iron and electricity.
- H2-EAF requires: natural gas, water, carbon, lime, pig iron and electricity.

The original models were constructed in Aspen Pro and translated into Python and added to H2I. The models were developed in conjunction with [Lawrence Berkeley National Laboratory (LBNL)](https://www.lbl.gov/).

The models implemented in H2I are:
- Natural Gas Electric Arc Furnace
  - `NaturalGasEAFPlantPerformanceComponent`
  - `NaturalGasEAFPlantCostComponent`
- Hydrogen Electric Arc Furnace
  - `HydrogenEAFPlantPerformanceComponent`
  - `HydrogenEAFPlantCostComponent`

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
