# H2Integrate - Holistic Hybrids Optimization and Design Tool

[![PyPI version](https://badge.fury.io/py/h2integrate.svg)](https://badge.fury.io/py/h2integrate)
![CI Tests](https://github.com/NREL/H2Integrate/actions/workflows/ci.yml/badge.svg)
[![image](https://img.shields.io/pypi/pyversions/h2integrate.svg)](https://pypi.python.org/pypi/h2integrate)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![DOI:10.5281/zenodo.17903150](https://zenodo.org/badge/DOI/10.5281/zenodo.17903149.svg)](https://zenodo.org/records/17903149)

H2Integrate is an open-source Python package for modeling and designing hybrid energy systems producing electricity, hydrogen, ammonia, steel, and other products.

```{note}
H2Integrate is under active development and may be missing features that existed in previous versions. H2Integrate v0.2.0 is the last version that uses the prior framework.
```

If you use this software in your work, please cite using the following BibTeX:

```bibtex
@software{brunik_2025_17903150,
  author = {Brunik, Kaitlin and
    Grant, Elenya and
    Thomas, Jared and
    Starke, Genevieve M and
    Martin, Jonathan and
    Ramos, Dakota and
    Koleva, Mariya and
    Reznicek, Evan and
    Hammond, Rob and
    Stanislawski, Brooke and
    Kiefer, Charlie and
    Irmas, Cameron and
    Vijayshankar, Sanjana and
    Riccobono, Nicholas and
    Frontin, Cory and
    Clark, Caitlyn and
    Barker, Aaron and
    Gupta, Abhineet and
    Kee, Benjamin (Jamie) and
    King, Jennifer and
    Jasa, John and
    Bay, Christopher},
  title = {H2Integrate: Holistic Hybrids Optimization and Design Tool},
  month = dec,
  year = 2025,
  publisher = {Zenodo},
  version = {0.4.0},
  doi = {10.5281/zenodo.17903150},
  url = {https://doi.org/10.5281/zenodo.17903150},
}
```

## What is H2Integrate?

H2Integrate is designed to be flexible and extensible, allowing users to create their own components and models for various energy systems.
The tool currently includes renewable energy generation (wind, solar, wave, tidal), battery storage, hydrogen, ammonia, methanol, and steel technologies.
Other elements such as desalination systems, pipelines, compressors, and storage systems can also be included as developed by users.
Some modeling capabilities in H2Integrate are provided by integrating existing tools, such as [HOPP](https://github.com/NREL/HOPP), [PySAM](https://github.com/NREL/pysam), [ORBIT](https://github.com/wisdem/ORBIT), and [ProFAST](https://github.com/NREL/ProFAST).
The H2Integrate tool is built on top of [NASA's OpenMDAO framework](https://github.com/OpenMDAO/OpenMDAO/), which provides a powerful and flexible environment for modeling and optimization.

```{note}
H2Integrate was previously known as GreenHEART. The name was updated to H2Integrate to better reflect its expanded capabilities and focus on integrated energy systems.
```

## How does H2Integrate work?

H2Integrate models energy systems on a yearly basis using hourly timesteps (i.e., 8760 operational data points across a year).
Results from these simulations are then processed across the project's lifecycle to provide insights into the system's performance, costs, and financial viability.
Depending on the models used and the size of the system, H2Integrate can simulate systems ranging from the kW to GW scale in seconds on a personal computer.
Additionally, H2Integrate tracks the flow of electricity, molecules (e.g., hydrogen, ammonia, methanol), and other products (e.g., steel) between different technologies in the energy system.


H2Integrate models hybrid energy systems by:
- Generating electricity output profiles from renewable energy sources (e.g., wind, solar, hydro) and storage systems (e.g., batteries, pumped hydro, vanadium flow batteries)
- Modeling the performance of hydrogen electrolyzers, steel furnaces, methanol plants, or ammonia synthesis systems using the generated electricity profiles
- Performing techno-economic analysis of the system to evaluate its costs and financial viability

This process is shown for an example energy system in the figure below:

![H2Integrate Splash Image](./splash_image.png)

## How does H2Integrate differ from other tools?

H2Integrate is developed at NREL, which has a long history of developing high-quality tools for renewable energy systems.
Although there are many tools available for modeling hybrid energy systems, H2Integrate is unique in its focus on component-level modeling and design including nonlinear physics models, as well as its modularity and extensibility.
H2Integrate stands out by offering a modular approach that models the entire energy system, from generation to end-use products such as hydrogen, ammonia, methanol, and steel, which is a capability not commonly found in other tools.

[REopt](https://reopt.nrel.gov/tool) is similar to H2Integrate in that it models hybrid energy systems, though it is a higher-level tool that focuses on linear optimization.
One significant difference is that REopt can accommodate various external loads such as steel or ammonia, as long as the user provides the load profiles for those end-uses.
H2Integrate models the processes themselves and does not require the user to provide a load profile, instead modeling what the load profile would be based on physics-based or analytical models.

[SAM](https://sam.nrel.gov/) is another relevant tool (that H2Integrate partially uses), which gives more detailed performance and financial modeling capabilities than REopt.
Like REopt, SAM also does not model loads or end-uses but accepts timeseries data of the loads for design purposes.

H2Integrate goes into more component-level details than those tools, especially in terms of nonlinear physics-based modeling and design.

```{tableofcontents}
```
